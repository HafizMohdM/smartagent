"""
SQL Generator — uses an LLM to convert natural-language queries into SQL.
Takes the database schema and user question, returns a SQL SELECT statement.
"""

import logging
import re
from typing import Set, Optional, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config.settings import settings
from backend.rag.embeddings.service import EmbeddingService
from backend.data.retrieval.hybrid_retriever import HybridTableRetriever

logger = logging.getLogger(__name__)

SQL_GENERATION_PROMPT = """You are a production-grade database AI assistant.

---

STEP 1: DETECT INTENT

Classify user query into ONE:

1. METADATA_REQUEST
   (Examples: show tables, list tables, what tables exist)

2. TABLE_LOOKUP
   (Examples: employees, attendance table)

3. DATA_QUERY
   (Examples: attendance of Hazel, employee names, salaries)

---

STEP 2: RESPONSE RULES

A. METADATA_REQUEST:
Return ONLY:
TYPE: METADATA
DATA:
* table1
* table2

NO SQL and NO explanation.

---

B. TABLE_LOOKUP:
Return ONLY:
TYPE: LOOKUP
DATA: <best_matching_table>

NO SQL and NO explanation.

---

C. DATA_QUERY:
Return ONLY:
TYPE: SQL
QUERY:
SELECT ...

STRICT RULES:
* Use ONLY tables from SCHEMA
* Use ONLY columns from SCHEMA
* Use RELATIONSHIPS for joins
* NEVER invent tables or columns
* RETURN EXACTLY ONE SQL QUERY
* DO NOT explain anything

If data is missing:
TYPE: ERROR
MESSAGE: Required data not found in schema

---

STEP 3: FALLBACK (ANTI-FAIL)
* If keyword match exists → use it
* If semantic weak → still pick the best match
* ONLY error if absolutely nothing matches

---

SCHEMA:
{filtered_schema}

RELATIONSHIPS:
{filtered_relationships}
"""


class SQLGenerator:
    """Generates SQL from natural language using an LLM."""

    def __init__(self):
        from pydantic import SecretStr
        self._llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=0,
        )
        self._embedding_service = EmbeddingService()
        self._hybrid_retriever = HybridTableRetriever(self._embedding_service)

    async def generate(self, user_query: str, schema: dict, connection_id: Optional[str] = None, error_context: str = None) -> str:
        """
        Generate a SQL query from a natural-language question.

        Args:
            user_query:    The user's natural-language question.
            schema:        The database schema dict (table → columns).
            error_context: Optional error from a previous failed execution.

        Returns:
            A SQL SELECT string.
        """
        # 1. Retrieve relevant tables using Hybrid Table Retrieval
        relevant_table_names = await self._hybrid_retriever.aget_relevant_tables(
            user_query, schema, connection_id=connection_id, limit=5
        )
        
        # SMALL FIX: Force mapping for common failure terms
        if "employee" in user_query.lower() and "employee_employee" in schema:
            if "employee_employee" not in relevant_table_names:
                # Add to start of list as high priority
                relevant_table_names = ["employee_employee"] + relevant_table_names
        
        # If no tables matched, we still proceed to the LLM to allow for METADATA_REQUEST 
        # or general assistance, providing a small sample of the schema.
        if not relevant_table_names:
            logger.info("No tables matched. Providing schema sample to LLM for intent detection.")
            relevant_table_names = list(schema.keys())[:5]

        # 2. Filter schema and format for the prompt
        pruned_schema = {name: schema[name] for name in relevant_table_names if name in schema}
        formatted_schema, formatted_relationships = await self._format_schema(pruned_schema, connection_id)
        
        logger.info(f"Using following tables in prompt: {list(pruned_schema.keys())}")

        messages = [
            SystemMessage(content=SQL_GENERATION_PROMPT.format(
                filtered_schema=formatted_schema,
                filtered_relationships=formatted_relationships
            )),
            HumanMessage(content=user_query),
        ]

        if error_context:
            messages.append(
                SystemMessage(content=f"Your previous query failed with this error: {error_context}. Please fix it.")
            )

        response = await self._llm.ainvoke(messages)
        sql = response.content.strip()

        # Strip markdown code fences if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            sql = sql.strip()

        logger.info(f"Generated SQL: {sql[:200]}")
        return sql

    def _prune_schema(self, user_query: str, schema: dict) -> dict:
        """
        Select only the tables likely to be relevant to the user query.
        Uses keyword matching and foreign key expansion.
        """
        relevant_tables: Set[str] = set()
        query_lower = user_query.lower()

        # Split query into keywords (longer than 2 chars) for matching
        query_keywords = [w for w in re.findall(r'\w+', query_lower) if len(w) > 2]

        # 1. Direct keyword match with table names
        for table_name in schema.keys():
            t_name_lower = table_name.lower()
            if any(kw in t_name_lower for kw in query_keywords):
                relevant_tables.add(table_name)
        
        # 2. Match with column names (if query is specific)
        for table_name, info in schema.items():
            if table_name in relevant_tables:
                continue
            for col in info.get("columns", []):
                col_name_lower = col['name'].lower()
                if any(kw in col_name_lower for kw in query_keywords):
                    relevant_tables.add(table_name)
                    break

        # 3. Expansion: add tables related via foreign keys to the already selected tables
        # This helps the LLM generate JOINs even if the related table isn't mentioned by name.
        # Fixed to 1 pass for token-saving: A -> B joins are caught.
        # If the result exceeds MAX_TABLES, we prioritize keywords.
        MAX_TABLES = 12
        if len(relevant_tables) < MAX_TABLES:
            expanded_tables = set(relevant_tables)
            for table_name in list(relevant_tables):
                # Outbound FKs
                fks = schema[table_name].get("foreign_keys", [])
                for fk in fks:
                    referred = fk.get("referred_table")
                    if referred in schema:
                        expanded_tables.add(referred)
                
                # Inbound FKs (Look through all other tables for FKs pointing to this one)
                for other_table, other_info in schema.items():
                    for other_fk in other_info.get("foreign_keys", []):
                        if other_fk.get("referred_table") == table_name:
                            expanded_tables.add(other_table)
            
            # Use limited expansion if it fits
            if len(expanded_tables) <= MAX_TABLES:
                relevant_tables = expanded_tables
            else:
                # If too many tables were expanded, only take the first MAX_TABLES
                # or just stick to relevant ones if expansion is too large.
                relevant_tables = set(list(expanded_tables)[:MAX_TABLES])

        # 4. Final Fallback: if still nothing found, return the top 15 tables with columns
        # Instead of empty columns, this gives the LLM a better chance to identify the right table
        if not relevant_tables:
            logger.warning("No relevant tables found via keyword matching. Returning first 15 tables.")
            return {k: v for k, v in list(schema.items())[:15]}

        # Return only the subset of the schema
        return {k: v for k, v in schema.items() if k in relevant_tables}

    async def _format_schema(self, schema: dict, connection_id: Optional[str] = None) -> (str, str):
        """Format schema dict into a readable string for the LLM prompt.
        Enforces the new production format: Table, Columns, Description, and RELATIONSHIPS.
        """
        schema_lines = []
        relationship_lines = []
        
        # Track all selected tables to filter relationships accurately
        selected_tables = set(schema.keys())
        
        for table_name in selected_tables:
            # Fetch metadata including pre-calculated relationships and description
            metadata = await self._hybrid_retriever.get_table_metadata(table_name, connection_id)
            
            description = metadata.get("description", "No description available.")
            col_list = metadata.get("columns", [])
            if not col_list:
                # Fallback to schema if metadata is missing columns
                col_list = [c['name'] for c in schema[table_name].get("columns", [])]
            
            col_names = ", ".join(col_list)

            schema_lines.append(f"Table: {table_name}")
            schema_lines.append(f"Columns: {col_names}")
            schema_lines.append(f"Description: {description}\n")
            
            # Use pre-calculated relationships if available
            fks = metadata.get("relationships", [])
            for fk in fks:
                referred_table = fk.get("referred_table")
                # Only include relationships where BOTH tables are in the selected subset
                if referred_table in selected_tables:
                    relationship_lines.append(f"{table_name}.{fk['column']} → {referred_table}.{fk['referred_column']}")

        # Combine Schema and RELATIONSHIPS section
        unique_rel = sorted(list(set(relationship_lines)))
        
        formatted_schema = "\n".join(schema_lines)
        formatted_relationships = "\n".join(unique_rel) if unique_rel else "No explicit relationships provided."
        
        return formatted_schema, formatted_relationships
