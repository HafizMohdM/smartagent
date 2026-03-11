"""
SQL Executor — runs validated SQL queries against the connected database
and formats results for the agent.
"""

import logging
import time
from typing import Any, Dict

from backend.services.database.connector import DatabaseConnector

logger = logging.getLogger(__name__)

MAX_ROWS = 500   # Safety cap on returned rows
MAX_CELL_LENGTH = 1000  # Truncate overly long cell values


class SQLExecutor:
    """Executes validated SQL and returns formatted results."""

    def __init__(self, connector: DatabaseConnector):
        self._connector = connector

    async def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute a SQL query and return structured results.

        Returns:
            {
                "columns": [...],
                "rows": [[...], ...],
                "row_count": int,
                "execution_time_ms": float,
                "truncated": bool,
            }
        """
        if not self._connector.is_connected:
            raise ConnectionError("Database is not connected.")

        start = time.perf_counter()
        raw_results = await self._connector.execute_query(sql)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if not raw_results:
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": round(elapsed_ms, 2),
                "truncated": False,
            }

        columns = list(raw_results[0].keys())
        truncated = len(raw_results) > MAX_ROWS
        rows_to_return = raw_results[:MAX_ROWS]

        # Truncate overly long cell values
        formatted_rows = []
        for row in rows_to_return:
            formatted_row = []
            for col in columns:
                val = row[col]
                str_val = str(val) if val is not None else None
                if str_val and len(str_val) > MAX_CELL_LENGTH:
                    str_val = str_val[:MAX_CELL_LENGTH] + "…"
                formatted_row.append(str_val if str_val != "None" else None)
            formatted_rows.append(formatted_row)

        logger.info(
            f"Query executed: {len(raw_results)} rows in {elapsed_ms:.1f}ms"
            f"{' (truncated)' if truncated else ''}"
        )

        return {
            "columns": columns,
            "rows": formatted_rows,
            "row_count": len(raw_results),
            "execution_time_ms": round(elapsed_ms, 2),
            "truncated": truncated,
        }
