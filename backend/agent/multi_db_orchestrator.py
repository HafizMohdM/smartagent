"""
MultiDBQueryOrchestrator — runs the same natural-language query against
multiple databases in parallel and merges the results.

Rules:
  - Each DB is queried independently (no cross-DB JOINs).
  - One DB failing does NOT fail the whole response.
  - If all DBs return the same column structure → rows are merged.
  - Otherwise → results are returned as separate sections keyed by DB name.
  - Security: connection ownership is validated before execution.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.connector.connector import DatabaseConnector
from backend.data.executor.generator import SQLGenerator, normalize_query
from backend.data.executor.validator import SQLValidator
from backend.data.executor.executor import SQLExecutor
from backend.agent.utils.sql_parser import SQLParser
from backend.security.encryption import decrypt_password

logger = logging.getLogger(__name__)

_PER_DB_TIMEOUT = 30  # seconds


class MultiDBQueryOrchestrator:
    """Execute a NL query against multiple databases in parallel."""

    def __init__(self):
        self._generator  = SQLGenerator()
        self._validator  = SQLValidator()

    async def run(
        self,
        query: str,
        connections: List[Any],          # list of DBConnection ORM objects
        history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Args:
            query:       Natural-language user query.
            connections: Validated DBConnection ORM objects (already ownership-checked).
            history:     Conversation history (passed to SQL generator for context).

        Returns:
            {
              "results": [
                {"database": "<name>", "connection_id": "...", "data": [...], "sql": "...", "error": null},
                ...
              ],
              "merged": True/False,
              "summary": "<text>",
            }
        """
        all_db_names = [conn.connection_name for conn in connections]
        tasks = [
            self._query_single_db(query, conn, all_db_names)
            for conn in connections
        ]
        raw_results: List[Dict] = await asyncio.gather(*tasks, return_exceptions=False)

        # Separate successes from failures
        successes = [r for r in raw_results if not r.get("error")]
        failures  = [r for r in raw_results if r.get("error")]

        for f in failures:
            logger.warning(f"[MultiDB] DB '{f['database']}' failed: {f['error']}")

        # Attempt merge if all successful results share the same columns
        merged = False
        if len(successes) > 1:
            col_sets = [frozenset(r["columns"]) for r in successes if r.get("columns")]
            if len(set(col_sets)) == 1:
                merged_rows = []
                for r in successes:
                    for row in r.get("data", []):
                        merged_rows.append({**row, "_source_db": r["database"]})
                merged = True
                return {
                    "results": raw_results,
                    "merged": True,
                    "merged_rows": merged_rows,
                    "merged_columns": list(col_sets.pop()) + ["_source_db"],
                    "summary": self._build_summary(raw_results, merged=True),
                }

        return {
            "results": raw_results,
            "merged": False,
            "summary": self._build_summary(raw_results, merged=False),
        }

    async def _query_single_db(self, query: str, conn: Any, all_db_names: List[str]) -> Dict[str, Any]:
        base = {
            "database":      conn.connection_name,
            "connection_id": str(conn.id),
            "data":          [],
            "columns":       [],
            "sql":           None,
            "error":         None,
            "row_count":     0,
            "execution_ms":  0,
        }
        t0 = time.monotonic()
        connector = DatabaseConnector()
        try:
            plaintext = decrypt_password(conn.encrypted_password)
            await asyncio.wait_for(
                connector.connect(
                    host=conn.host, port=conn.port,
                    database=conn.database_name,
                    username=conn.username, password=plaintext,
                    connection_id=str(conn.id),
                ),
                timeout=_PER_DB_TIMEOUT,
            )

            schema = connector.get_schema()
            normalized = normalize_query(query)

            # Generate SQL
            sql_raw = await asyncio.wait_for(
                self._generator.generate(
                    user_query=normalized,
                    schema=schema,
                    connection_id=str(conn.id),
                    db_name=conn.connection_name,
                    all_db_names=all_db_names,
                ),
                timeout=_PER_DB_TIMEOUT,
            )

            # Handle Intent-Based Outputs (METADATA, LOOKUP, CLARIFICATION, ERROR)
            upper_sql = sql_raw.lstrip().upper()
            if upper_sql.startswith("TYPE: METADATA") or upper_sql.startswith("TYPE: LOOKUP"):
                parts = sql_raw.split("DATA:")
                if len(parts) > 1:
                    raw_items = parts[1].strip().split('\n')
                    items = [item.strip("*- \t") for item in raw_items if item.strip()]
                    base["data"] = [{"Result": item} for item in items]
                    base["columns"] = ["Result"]
                    base["row_count"] = len(items)
                    base["sql"] = sql_raw  # Keep original output
                return base
                
            if upper_sql.startswith("TYPE: ERROR") or upper_sql.startswith("TYPE: CLARIFICATION"):
                parts = sql_raw.split("MESSAGE:") if "MESSAGE:" in sql_raw else sql_raw.split("DATA:")
                msg = parts[1].strip() if len(parts) > 1 else sql_raw.split('\n', 1)[-1].strip()
                base["error"] = msg
                return base

            pure_sql = SQLParser.extract_sql(sql_raw)
            if not pure_sql:
                base["error"] = f"Could not generate SQL for this database: {sql_raw[:200]}"
                return base

            # Validate
            is_valid, reason = self._validator.validate(pure_sql)
            if not is_valid:
                base["error"] = f"SQL validation failed: {reason}"
                base["sql"] = pure_sql
                return base

            base["sql"] = pure_sql

            # Execute
            executor = SQLExecutor(connector)
            result = await asyncio.wait_for(
                executor.execute(pure_sql),
                timeout=_PER_DB_TIMEOUT,
            )

            rows    = result.get("rows", [])
            columns = result.get("columns", [])
            base.update({
                "data":         rows,
                "columns":      columns,
                "row_count":    len(rows),
                "execution_ms": int((time.monotonic() - t0) * 1000),
            })

        except asyncio.TimeoutError:
            base["error"] = f"Query timed out after {_PER_DB_TIMEOUT}s"
        except Exception as e:
            logger.error(f"[MultiDB] Error on '{conn.connection_name}': {e}", exc_info=True)
            base["error"] = str(e)
        finally:
            try:
                await connector.disconnect()
            except Exception:
                pass

        return base

    @staticmethod
    def _build_summary(results: List[Dict], merged: bool) -> str:
        parts = []
        for r in results:
            if r.get("error"):
                parts.append(f"**{r['database']}**: ❌ {r['error']}")
            else:
                parts.append(f"**{r['database']}**: {r['row_count']} rows")
        header = "Results merged across databases." if merged else "Results per database:"
        return header + "\n" + "\n".join(parts)
