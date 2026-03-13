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
        question = params.get("question", "")
        if not question:
            return ToolResult(success=False, error="Missing 'question' parameter.")

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
            sql = await self._sql_generator.generate(user_query=question, schema=schema)

            # 4. SQL Validation
            logger.info(f"[Pipeline] Step 3: Validating SQL: {sql[:120]}...")
            is_valid, reason = self._sql_validator.validate(sql)
            if not is_valid:
                return ToolResult(
                    success=False,
                    error=f"SQL validation failed: {reason}",
                    metadata={"generated_sql": sql},
                )

            # 5. SQL Execution
            logger.info("[Pipeline] Step 4: Executing SQL")
            executor = SQLExecutor(connector)
            results = await executor.execute(sql)

            # 6. Result Formatting
            logger.info(f"[Pipeline] Step 5: Returning {results['row_count']} rows")
            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "generated_sql": sql,
                    "row_count": results["row_count"],
                    "execution_time_ms": results["execution_time_ms"],
                },
            )

        except ConnectionError as e:
            return ToolResult(success=False, error=f"Database connection error: {str(e)}")
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
    ) -> Dict[str, str]:
        """
        Connect to a database for a specific session.
        Credentials should already be decrypted before reaching here.
        """
        connector = DatabaseConnector()
        result = await connector.connect(
            host=host, port=port, database=database,
            username=username, password=password,
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
