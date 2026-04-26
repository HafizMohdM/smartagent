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
        """Run the full database query pipeline via SchemaAwareSQLPipeline."""
        from backend.data.executor.generator import normalize_query, remove_limit
        from backend.data.executor.sql_pipeline import SchemaAwareSQLPipeline

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
            connection_id = getattr(connector, "_connection_id", None)
            
            # 3. Create trace context
            trace_context = {
                "request_id": session_id,  # Using session_id as anchor for now
                "connection_id": connection_id,
                "tool": "database_query"
            }

            # 4. Run through the centralized pipeline
            logger.info("[Pipeline] Delegating to SchemaAwareSQLPipeline")
            from backend.data.executor.contract import validate_db_result, get_error_fallback
            pipeline = SchemaAwareSQLPipeline()
            result = await pipeline.run(
                query=question,
                schema=schema,
                connector=connector,
                tenant_id=params.get("tenant_id"),
                connection_id=connection_id or params.get("connection_id"),
                report_mode=report_mode,
                trace_context=trace_context,
                semantic_context=params.get("semantic_context", ""),
            )

            # 5. Convert pipeline result to ToolResult with strict validation
            if result.success:
                tool_data = result.to_tool_data()
                # Final tool-layer validation (MANDATORY per senior req)
                validated_data = validate_db_result(tool_data, source="database_tool", trace_context=trace_context)
                
                return ToolResult(
                    success=True,
                    data=validated_data,
                    metadata={
                        "generated_sql": result.sql,
                        "intent": result.intent,
                        "domain": result.domain,
                        "repairs_applied": result.repairs_applied,
                        **result.meta,
                    },
                )
            else:
                fallback = get_error_fallback(result.error_message or "Query processing failed.", source="database_tool", trace_context=trace_context)
                return ToolResult(
                    success=False,
                    error=result.error_message or "Query processing failed.",
                    data=fallback,
                    metadata={
                        "generated_sql": result.sql,
                        "intent": result.intent,
                    },
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
