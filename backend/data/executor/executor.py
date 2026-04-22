"""
SQL Executor — runs validated SQL queries against the connected database
and formats results for the agent.
"""

import logging
import time
from typing import Any, Dict, Optional

from backend.data.connector.connector import DatabaseConnector
from backend.data.executor.contract import validate_db_result, get_error_fallback

logger = logging.getLogger(__name__)

MAX_ROWS = 1000   # Production cap on returned rows
MAX_CELL_LENGTH = 500  # Truncate overly long cell values


class SQLExecutor:
    """Executes validated SQL and returns strictly formatted results."""

    def __init__(self, connector: DatabaseConnector):
        self._connector = connector

    async def execute(self, sql: str, trace_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a SQL query and return strictly structured results.

        Returns:
            {
                "rows": List[Dict],
                "columns": List[str],
                "meta": {
                    "row_count": int,
                    "execution_time_ms": float,
                    "sql": str,
                    "truncated": bool,
                    "version": "v1"
                }
            }
        """
        ctx = trace_context or {}
        if not self._connector.is_connected:
            raise ConnectionError("Database is not connected.")

        start = time.perf_counter()
        try:
            raw_results = await self._connector.execute_query(sql)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

            if not raw_results:
                result = {
                    "rows": [],
                    "columns": [],
                    "meta": {
                        "row_count": 0,
                        "execution_time_ms": elapsed_ms,
                        "sql": sql,
                        "truncated": False,
                        "version": "v1"
                    }
                }
                return validate_db_result(result, source="executor", trace_context=ctx)

            columns = list(raw_results[0].keys())
            truncated = len(raw_results) > MAX_ROWS
            rows_to_process = raw_results[:MAX_ROWS]

            # Format rows as dicts and enforce cell limits
            formatted_rows = []
            for row in rows_to_process:
                formatted_row = {}
                for col in columns:
                    val = row[col]
                    # We keep non-string types as they are (int, float, bool, etc.)
                    # only truncate if it's a long string
                    if isinstance(val, str) and len(val) > MAX_CELL_LENGTH:
                        val = val[:MAX_CELL_LENGTH] + "…"
                    formatted_row[col] = val
                formatted_rows.append(formatted_row)

            result = {
                "rows": formatted_rows,
                "columns": columns,
                "meta": {
                    "row_count": len(raw_results),
                    "execution_time_ms": elapsed_ms,
                    "sql": sql,
                    "truncated": truncated,
                    "version": "v1"
                }
            }

            # MANDATORY: Self-validate before returning
            return validate_db_result(result, source="executor", trace_context=ctx)

        except Exception as e:
            logger.error({
                "event": "executor_failure",
                "error": str(e),
                "sql": sql,
                **ctx
            })
            return get_error_fallback(str(e), source="executor", trace_context=ctx)

