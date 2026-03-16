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

Rules:
1. Generate ONLY SELECT queries. Never generate INSERT, UPDATE, DELETE, DROP,
   ALTER, TRUNCATE, or any other data-modification statement.
2. Use proper JOINs when the question involves multiple tables.
3. Use aggregate functions (COUNT, SUM, AVG, etc.) when appropriate.
4. Add LIMIT 50 to prevent excessive result sets unless explicitly asked otherwise.
5. Use table and column aliases for readability.
6. Return ONLY the raw SQL query, nothing else. No markdown, no explanation."""


class SQLGenerator:
    """Generates SQL from natural language using an LLM."""

    def __init__(self):
        from pydantic import SecretStr
        self._llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=0,
        )

    async def generate(self, user_query: str, schema: dict) -> str:
        """
        Generate a SQL query from a natural-language question.

        Args:
            user_query: The user's natural-language question.
            schema:     The database schema dict (table → columns).

        Returns:
            A SQL SELECT string.
        """
        # Prune schema if it's too large to fit in the prompt comfortably
        schema_to_use = schema
        if len(schema) > 15:
            logger.info(f"Large schema detected ({len(schema)} tables). Pruning for prompt...")
            schema_to_use = self._prune_schema(user_query, schema)
            logger.info(f"Pruned schema to {len(schema_to_use)} relevant tables.")

        schema_text = self._format_schema(schema_to_use)

        messages = [
            SystemMessage(content=SQL_GENERATION_PROMPT.format(schema=schema_text)),
            HumanMessage(content=f"Question: {user_query}"),
        ]

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

        # 1. Direct keyword match with table names
        for table_name in schema.keys():
            # Match whole words to avoid partial matches (e.g., 'user' matching 'users_log')
            if re.search(rf"\b{re.escape(table_name.lower())}\b", query_lower):
                relevant_tables.add(table_name)
        
        # 2. Match with column names (if query is specific)
        if not relevant_tables:
            for table_name, info in schema.items():
                for col in info.get("columns", []):
                    if re.search(rf"\b{re.escape(col['name'].lower())}\b", query_lower):
                        relevant_tables.add(table_name)
                        break

        # 3. Expansion: add tables related via foreign keys to the already selected tables
        # This helps the LLM generate JOINs even if the related table isn't mentioned by name.
        expanded_tables = set(relevant_tables)
        for table_name in relevant_tables:
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

        # 4. Final Fallback: if still nothing found, return a limited set of table names
        # so the LLM can at least try to guess or ask for more info.
        if not expanded_tables:
            logger.warning("No relevant tables found via keyword matching. Returning table names only.")
            # Special case: return just the table names instead of full definitions if huge
            if len(schema) > 50:
                return {name: {"columns": [], "note": "Empty columns due to pruning"} for name in list(schema.keys())[:50]}
            return schema

        # Return only the subset of the schema
        return {k: v for k, v in schema.items() if k in expanded_tables}

    @staticmethod
    def _format_schema(schema: dict) -> str:
        """Format schema dict into a readable string for the LLM prompt."""
        lines = []
        for table_name, table_info in schema.items():
            cols = table_info.get("columns", [])
            col_defs = ", ".join(
                f"{c['name']} ({c['type']})" for c in cols
            )
            pk = ", ".join(table_info.get("primary_keys", []))
            fks = table_info.get("foreign_keys", [])

            lines.append(f"Table: {table_name}")
            lines.append(f"  Columns: {col_defs}")
            if pk:
                lines.append(f"  Primary Key: {pk}")
            for fk in fks:
                lines.append(
                    f"  FK: {fk['columns']} → {fk['referred_table']}({fk['referred_columns']})"
                )
            lines.append("")
        return "\n".join(lines)
