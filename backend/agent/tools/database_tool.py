"""
Database Tool — the top-level tool that implements the full database query pipeline.

Pipeline:
    User Query → Schema Retrieval → SQL Generation → SQL Validation
    → SQL Execution → Result Formatting

Registered as "database_query" in the ToolRegistry so the agent
orchestrator can discover and invoke it automatically.
"""

import logging
from typing import Any, Dict

from .base import BaseTool, ToolResult
from backend.data.connector.connector import DatabaseConnector
from backend.data.executor.generator import SQLGenerator
from backend.data.executor.validator import SQLValidator
from backend.data.executor.executor import SQLExecutor
from backend.memory.session.manager import SessionManager

logger = logging.getLogger(__name__)


class DatabaseTool(BaseTool):
    """
    End-to-end database query tool.

    Expects a connected DatabaseConnector to be stored in the session.
    Takes a natural-language question, generates SQL, validates it,
    executes it, and returns structured results.
    """

    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager
        self._connectors: Dict[str, DatabaseConnector] = {}  # session_id → connector
        self._sql_generator = SQLGenerator()
        self._sql_validator = SQLValidator()

    # ── BaseTool interface ─────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "database_query"

    @property
    def description(self) -> str:
        return (
            "Query a connected PostgreSQL database using natural language. "
            "Provide a 'question' parameter with your data question. "
            "The tool will generate, validate, and execute a safe SQL query, "
            "then return the results."
        )

    async def execute(self, params: Dict[str, Any], session_id: str) -> ToolResult:
        """Run the full database query pipeline."""
        from backend.data.executor.generator import normalize_query, remove_limit

        question = params.get("question", "")
        if not question:
            return ToolResult(success=False, error="Missing 'question' parameter.")

        # Detect report mode: analytical queries that should not be LIMITed
        REPORT_KEYWORDS = {
            "report", "summary", "total", "count", "average", "avg", "sum",
            "all employees", "all records", "full data", "breakdown", "analytics",
            "how many", "per department", "per month", "per year", "trend",
        }
        question_lower = question.lower()
        report_mode = any(kw in question_lower for kw in REPORT_KEYWORDS)

        # Normalize vague / name-only inputs before entering the pipeline
        question = normalize_query(question)

        # 1. Get the connector for this session
        connector = self._connectors.get(session_id)
        if connector is None or not connector.is_connected:
            return ToolResult(
                success=False,
                error="No database connection found. Please connect to a database first.",
            )

        try:
            # 2. Schema Retrieval
            logger.info(f"[Pipeline] Step 1: Retrieving schema for session {session_id}")
            schema = connector.get_schema()

            # 3. SQL Generation
            logger.info("[Pipeline] Step 2: Generating SQL from user question")
            connection_id = getattr(connector, "_connection_id", None)
            sql = await self._sql_generator.generate(
                user_query=question,
                schema=schema,
                connection_id=connection_id,
                report_mode=report_mode,
            )

            # 4. Response Parsing & Validation
            logger.info(f"[Pipeline] Step 3: Validating generator output")
            
            from backend.agent.utils.sql_parser import SQLParser
            pure_sql = SQLParser.extract_sql(sql)
            
            # --- Non-SQL Responses (Metadata/Lookup) ---
            if not pure_sql:
                resp_type = SQLParser.get_response_type(sql)
                if resp_type in ["metadata", "lookup"]:
                    return ToolResult(
                        success=True,
                        data={"message": sql, "type": resp_type},
                        metadata={"generated_sql": None},
                    )
                return ToolResult(
                    success=False,
                    error=sql,
                    metadata={"generated_sql": None},
                )

            # --- SQL Validation ---
            # Safety net: strip LIMIT in report mode even if LLM ignored the instruction
            if report_mode:
                pure_sql = remove_limit(pure_sql)

            is_valid, reason = self._sql_validator.validate(pure_sql)
            if not is_valid:
                return ToolResult(
                    success=False,
                    error=f"SQL validation failed: {reason}",
                    metadata={"generated_sql": pure_sql},
                )

            # 5. SQL Execution & Self-Correction Loop
            logger.info("[Pipeline] Step 4: Executing SQL")
            from backend.data.executor import executor
            sql_executor = executor.SQLExecutor(connector)

            try:
                results = await sql_executor.execute(pure_sql)
                return ToolResult(
                    success=True,
                    data=results,
                    metadata={"generated_sql": pure_sql},
                )
            except Exception as e:
                logger.warning(f"Initial SQL execution failed: {e}. Attempting self-correction...")

                # Retry once with error context
                corrected_sql_raw = await self._sql_generator.generate(
                    user_query=question,
                    schema=schema,
                    connection_id=connection_id,
                    error_context=str(e),
                    report_mode=report_mode,
                )
                corrected_sql = SQLParser.extract_sql(corrected_sql_raw) or corrected_sql_raw
                if report_mode:
                    corrected_sql = remove_limit(corrected_sql)
                
                try:
                    results = await sql_executor.execute(corrected_sql)
                    return ToolResult(
                        success=True,
                        data=results,
                        metadata={"generated_sql": corrected_sql},
                    )
                except Exception as e2:
                    return ToolResult(
                        success=False,
                        error=f"SQL execution failed after correction: {e2}",
                        metadata={"generated_sql": corrected_sql},
                    )
        except Exception as e:
            logger.error(f"Database tool error: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Unexpected error: {str(e)}")

    # ── Connection management ──────────────────────────────────────────

    async def connect(
        self,
        session_id: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        connection_id: str = None,
    ) -> Dict[str, str]:
        """
        Connect to a database for a specific session.
        Credentials should already be decrypted before reaching here.
        """
        connector = DatabaseConnector()
        result = await connector.connect(
            host=host, port=port, database=database,
            username=username, password=password,
            connection_id=connection_id,
        )
        self._connectors[session_id] = connector

        # Persist connection info in session (without password)
        await self._session_manager.store_connection(
            session_id,
            "database",
            {"host": host, "port": port, "database": database, "username": username},
        )

        return result

    async def disconnect(self, session_id: str) -> None:
        """Disconnect and clean up the database connection for a session."""
        connector = self._connectors.pop(session_id, None)
        if connector:
            await connector.disconnect()

    def is_connected(self, session_id: str) -> bool:
        """Check if a database connection exists for a session."""
        connector = self._connectors.get(session_id)
        return connector is not None and connector.is_connected
