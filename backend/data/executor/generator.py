"""
SQL Generator — uses an LLM to convert natural-language queries into SQL.
Takes the database schema and user question, returns a SQL SELECT statement.
"""

import logging
import re
from typing import Set

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config.settings import settings

logger = logging.getLogger(__name__)

SQL_GENERATION_PROMPT = """You are an expert SQL query generator.
Given a database schema and a natural-language question, generate a valid
PostgreSQL SELECT query that answers the question.

Database schema:
{schema}

Strict Generation Rules:
1. ONLY generate SELECT or WITH (CTE) statements. 
2. Categorically FORBIDDEN: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.
3. Use only the tables and columns explicitly listed in the schema.
4. If the schema is insufficient to answer the question, do not guess. Instead, start your response with an explanation in plain text (no SQL).
5. Always use proper JOINs via the Foreign Key (FK) information provided.
6. Add LIMIT 50 to prevent excessive result sets unless explicitly asked otherwise.
7. Return raw SQL or a plain text explanation. Do not use markdown code blocks."""


class SQLGenerator:
    """Generates SQL from natural language using an LLM."""

    def __init__(self):
        from pydantic import SecretStr
        self._llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=0,
        )

    async def generate(self, user_query: str, schema: dict, error_context: str = None) -> str:
        """
        Generate a SQL query from a natural-language question.

        Args:
            user_query:    The user's natural-language question.
            schema:        The database schema dict (table → columns).
            error_context: Optional error from a previous failed execution.

        Returns:
            A SQL SELECT string.
        """
        # Prune schema if it's too large to fit in the prompt comfortably (threshold lowered to 10)
        schema_to_use = schema
        if len(schema) > 10:
            logger.info(f"Large schema detected ({len(schema)} tables). Pruning for prompt...")
            schema_to_use = self._prune_schema(user_query, schema)
            logger.info(f"Pruned schema to {len(schema_to_use)} relevant tables.")

        schema_text = self._format_schema(schema_to_use)
        
        logger.info(f"Using following tables in prompt: {list(schema_to_use.keys())}")

        messages = [
            SystemMessage(content=SQL_GENERATION_PROMPT.format(schema=schema_text)),
            HumanMessage(content=f"Question: {user_query}"),
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

    @staticmethod
    def _format_schema(schema: dict) -> str:
        """Format schema dict into a readable string for the LLM prompt.
        Optimized for token usage: compact representation.
        """
        lines = []
        for table_name, table_info in schema.items():
            cols = table_info.get("columns", [])
            col_names = ", ".join(f"{c['name']}" for c in cols)
            fks = table_info.get("foreign_keys", [])

            lines.append(f"T:{table_name}({col_names})")
            for fk in fks:
                lines.append(
                    f" FK:{fk['columns']}->{fk['referred_table']}({fk['referred_columns']})"
                )
        return "\n".join(lines)
