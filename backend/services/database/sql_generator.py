"""
SQL Generator — uses an LLM to convert natural-language queries into SQL.
Takes the database schema and user question, returns a SQL SELECT statement.
"""

import logging

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
        schema_text = self._format_schema(schema)

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
