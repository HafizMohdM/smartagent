import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data.connector.connector import DatabaseConnector
from backend.data.executor.executor import SQLExecutor
from backend.data.executor.schema_cache import schema_cache
from backend.models.db_connection import DBConnection
from backend.security.encryption import decrypt_password
from backend.config.settings import settings
from backend.agent.utils.sql_parser import SQLParser

from backend.data.executor.contract import validate_db_result, get_error_fallback

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent DB executions
execution_semaphore = asyncio.Semaphore(settings.MAX_PARALLEL_QUERIES)

async def _normalize_and_merge(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Union all columns across results and pad missing ones with None. Enforces sorted column order."""
    if not results:
        return []

    # Deterministic Column Ordering (MANDATORY per senior req)
    all_columns = set()
    for row in results:
        all_columns.update(row.keys())
    
    sorted_cols = sorted(list(all_columns))

    normalized = []
    for row in results:
        new_row = {col: row.get(col) for col in sorted_cols}
        normalized.append(new_row)
    
    return normalized

async def execute_sql_on_connection(
    conn: DBConnection, 
    sql: str, 
    timeout: float = settings.DEFAULT_DB_TIMEOUT,
    trace_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute raw SQL on a single connection with strict contract enforcement."""
    ctx = trace_context or {}
    t0 = time.monotonic()
    connector = DatabaseConnector()
    db_id = str(conn.id)
    db_name = conn.connection_name or conn.database_name
    
    # Update context with current connection
    ctx = {**ctx, "connection_id": db_id, "database_name": db_name}

    try:
        upper_sql = sql.lstrip().upper()

        # ── Intent-based responses (no DB execution needed) ──────────
        # These must still follow the contract
        if any(kw in upper_sql for kw in ["TYPE: METADATA", "TYPE: LOOKUP", "TYPE: TABLE_LOOKUP"]):
            parts = sql.split("DATA:")
            items = []
            if len(parts) > 1:
                raw_items = parts[1].strip().split('\n')
                items = [item.strip("*- \t") for item in raw_items if item.strip()]
            
            result = {
                "rows": [{"Result": item} for item in items],
                "columns": ["Result"],
                "meta": {
                    "row_count": len(items),
                    "execution_time_ms": 0,
                    "sql": sql,
                    "version": "v1"
                }
            }
            return validate_db_result(result, source="orchestrator_intent", trace_context=ctx)
            
        if "TYPE: ERROR" in upper_sql or "TYPE: CLARIFICATION" in upper_sql:
            parts = sql.split("MESSAGE:") if "MESSAGE:" in sql else sql.split("DATA:")
            msg = parts[1].strip() if len(parts) > 1 else sql.split('\n', 1)[-1].strip()
            return get_error_fallback(msg, source="orchestrator_intent", trace_context=ctx)

        # ── Schema Validation ────────────────────────────────────────
        required_tables = SQLParser.extract_tables(sql)
        if required_tables:
            available_tables = await schema_cache.get_tables(conn)
            if available_tables:
                missing = required_tables - available_tables
                if missing:
                    err_msg = f"Table(s) not found: {', '.join(sorted(missing))}"
                    return get_error_fallback(err_msg, source="orchestrator_schema", trace_context=ctx)

        # ── Execute query ────────────────────────────────────────────
        async with execution_semaphore:
            plaintext_password = decrypt_password(conn.encrypted_password)
            await asyncio.wait_for(
                connector.connect(
                    host=conn.host,
                    port=conn.port,
                    database=conn.database_name,
                    username=conn.username,
                    password=plaintext_password,
                    connection_id=db_id
                ),
                timeout=timeout
            )
            
            executor = SQLExecutor(connector)
            # Delegate to executor which now also returns the strict contract
            result = await asyncio.wait_for(executor.execute(sql, trace_context=ctx), timeout=timeout)
            
            # Inject source metadata into rows (for multi-DB traceability)
            for r in result["rows"]:
                r["_source_db"] = db_name
            
            if "_source_db" not in result["columns"]:
                result["columns"].append("_source_db")
            
            return validate_db_result(result, source="orchestrator_step", trace_context=ctx)

    except asyncio.TimeoutError:
        return get_error_fallback(f"Query timed out (>{timeout}s)", source="orchestrator_timeout", trace_context=ctx)
    except Exception as e:
        logger.error({
            "event": "orchestrator_connection_failure",
            "error": str(e),
            **ctx
        })
        return get_error_fallback(str(e), source="orchestrator_error", trace_context=ctx)
    finally:
        await connector.disconnect()

async def run_parallel_sql(
    connections: List[DBConnection],
    sql: str,
    timeout: float = settings.GLOBAL_QUERY_TIMEOUT,
    trace_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute SQL across multiple connections in parallel and merge results into strict contract."""
    ctx = trace_context or {}
    t_start = time.monotonic()
    
    tasks = {
        asyncio.create_task(execute_sql_on_connection(c, sql, settings.DEFAULT_DB_TIMEOUT, ctx)): c
        for c in connections
    }
    
    done, pending = await asyncio.wait(
        tasks.keys(),
        timeout=timeout
    )
    
    for p_task in pending:
        p_task.cancel()
        
    successful_results = []
    failed_sources = []
    
    for d_task in done:
        conn_obj = tasks[d_task]
        try:
            res = await d_task
            # Any result from execute_sql_on_connection is now a strict contract dict
            if res["meta"].get("error"):
                failed_sources.append({
                    "database_id": str(conn_obj.id),
                    "database_name": conn_obj.connection_name or conn_obj.database_name,
                    "error": res["meta"]["error"]
                })
            else:
                successful_results.append(res)
        except Exception as e:
            failed_sources.append({
                "database_id": str(conn_obj.id),
                "database_name": conn_obj.connection_name or conn_obj.database_name,
                "error": str(e)
            })

    for p_task in pending:
        conn_obj = tasks[p_task]
        failed_sources.append({
            "database_id": str(conn_obj.id),
            "database_name": conn_obj.connection_name or conn_obj.database_name,
            "error": "Global Timeout"
        })

    # Merge successful results
    all_rows = []
    for res in successful_results:
        all_rows.extend(res["rows"])
    
    # Deterministic normalization
    merged_rows = await _normalize_and_merge(all_rows)
    merged_columns = sorted(list(set().union(*(res["columns"] for res in successful_results)))) if successful_results else []
    
    execution_time_total = int((time.monotonic() - t_start) * 1000)
    
    result = {
        "rows": merged_rows,
        "columns": merged_columns,
        "meta": {
            "row_count": len(merged_rows),
            "execution_time_ms": execution_time_total,
            "sql": sql,
            "failed_sources": failed_sources,
            "version": "v1",
            "truncated": any(res["meta"].get("truncated") for res in successful_results)
        }
    }
    
    return validate_db_result(result, source="orchestrator_parallel", trace_context=ctx)

