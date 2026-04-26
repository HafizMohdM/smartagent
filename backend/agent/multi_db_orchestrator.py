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
        connections: List[Any],
        history: Optional[List[Dict]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
        semantic_context: Optional[Dict[str, str]] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a NL query against multiple databases in parallel and return the strict contract.
        """
        ctx = trace_context or {}
        semantic_contexts = semantic_context or {}
        all_db_names = [conn.connection_name for conn in connections]
        tasks = [
            self._query_single_db(query, conn, all_db_names, ctx, semantic_contexts.get(conn.connection_name, ""), tenant_id)
            for conn in connections
        ]
        # Each res is now a strict contract dict
        raw_results: List[Dict] = await asyncio.gather(*tasks, return_exceptions=False)

        success_results = [r for r in raw_results if not r["meta"].get("error")]
        failed_sources = [
            {
                "database_id": r["meta"].get("connection_id"),
                "database_name": r["meta"].get("database_name"),
                "error": r["meta"].get("error")
            }
            for r in raw_results if r["meta"].get("error")
        ]

        # ── Deterministic Merge ──────────────────────────────────────
        all_rows = []
        for r in success_results:
            all_rows.extend(r["rows"])

        from backend.data.executor.orchestrator import _normalize_and_merge
        from backend.data.executor.contract import validate_db_result
        
        merged_rows = await _normalize_and_merge(all_rows)
        # Unique sorted union of columns
        all_cols_set = set()
        for r in success_results:
            all_cols_set.update(r["columns"])
        
        merged_columns = sorted(list(all_cols_set))

        execution_time_total = int((time.monotonic() - time.monotonic()) * 1000) # Placeholder
        
        result = {
            "rows": merged_rows,
            "columns": merged_columns,
            "meta": {
                "row_count": len(merged_rows),
                "execution_time_ms": 0, # Calculated at end
                "sql": query,
                "failed_sources": failed_sources,
                "version": "v1",
                "merged": len(success_results) > 0,
                "individual_results": raw_results # Keep for debug/UI detail if needed
            }
        }
        
        return validate_db_result(result, source="multi_db_orchestrator", trace_context=ctx)

    async def _query_single_db(self, query: str, conn: Any, all_db_names: List[str], trace_context: Dict[str, Any], semantic_context: str = "", tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Query a single DB and return the strict contract."""
        db_id = str(conn.id)
        db_name = conn.connection_name
        ctx = {**trace_context, "connection_id": db_id, "database_name": db_name}
        
        from backend.data.executor.contract import get_error_fallback, validate_db_result
        
        t0 = time.monotonic()
        connector = DatabaseConnector()
        try:
            plaintext = decrypt_password(conn.encrypted_password)
            await asyncio.wait_for(
                connector.connect(
                    host=conn.host, port=conn.port,
                    database=conn.database_name,
                    username=conn.username, password=plaintext,
                    connection_id=db_id,
                ),
                timeout=_PER_DB_TIMEOUT,
            )

            schema = connector.get_schema()

            # ── Delegate to centralized pipeline ─────────────────────────
            from backend.data.executor.sql_pipeline import SchemaAwareSQLPipeline

            pipeline = SchemaAwareSQLPipeline()
            result = await asyncio.wait_for(
                pipeline.run(
                    query=query,
                    schema=schema,
                    connector=connector,
                    connection_id=db_id,
                    tenant_id=tenant_id,
                    db_name=db_name,
                    all_db_names=all_db_names,
                    trace_context=ctx,
                    semantic_context=semantic_context,
                ),
                timeout=_PER_DB_TIMEOUT,
            )

            # pipeline.run returns a PipelineResult, to_multi_db_format() is now strict
            pipeline_data = result.to_multi_db_format()
            
            # Inject source metadata into rows
            for r in pipeline_data["rows"]:
                r["_source_db"] = db_name
            if "_source_db" not in pipeline_data["columns"]:
                pipeline_data["columns"].append("_source_db")

            # Update meta with connection info
            pipeline_data["meta"].update({
                "connection_id": db_id,
                "database_name": db_name,
                "execution_time_ms": int((time.monotonic() - t0) * 1000)
            })

            return validate_db_result(pipeline_data, source="multi_db_single", trace_context=ctx)

        except asyncio.TimeoutError:
            return get_error_fallback(f"Query timed out after {_PER_DB_TIMEOUT}s", source="multi_db_single", trace_context=ctx)
        except Exception as e:
            logger.error(f"[MultiDB] Error on '{db_name}': {e}")
            return get_error_fallback(str(e), source="multi_db_single", trace_context=ctx)
        finally:
            await connector.disconnect()


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
