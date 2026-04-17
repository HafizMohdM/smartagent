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

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent DB executions
execution_semaphore = asyncio.Semaphore(settings.MAX_PARALLEL_QUERIES)

async def _normalize_and_merge(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Union all columns across results and pad missing ones with None."""
    if not results:
        return []

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
    timeout: float,
    request_id: str = "N/A"
) -> Dict[str, Any]:
    """Execute raw SQL on a single connection with timeout, telemetry, and schema validation."""
    t0 = time.monotonic()
    connector = DatabaseConnector()
    db_id = str(conn.id)
    db_name = conn.connection_name or conn.database_name

    try:
        upper_sql = sql.lstrip().upper()

        # ── Intent-based responses (no DB execution needed) ──────────
        if "TYPE: METADATA" in upper_sql or "TYPE: LOOKUP" in upper_sql or "TYPE: TABLE_LOOKUP" in upper_sql:
            parts = sql.split("DATA:")
            if len(parts) > 1:
                raw_items = parts[1].strip().split('\n')
                items = [item.strip("*- \t") for item in raw_items if item.strip()]
                return {
                    "success": True,
                    "database_id": db_id,
                    "database_name": db_name,
                    "rows": [{"Result": item} for item in items],
                    "columns": ["Result"],
                    "execution_time_ms": 0
                }
            
        if "TYPE: ERROR" in upper_sql or "TYPE: CLARIFICATION" in upper_sql:
            parts = sql.split("MESSAGE:") if "MESSAGE:" in sql else sql.split("DATA:")
            msg = parts[1].strip() if len(parts) > 1 else sql.split('\n', 1)[-1].strip()
            return {"success": False, "database_id": db_id, "database_name": db_name, "error": msg}

        # ── Schema Validation: check tables BEFORE executing ─────────
        required_tables = SQLParser.extract_tables(sql)
        if required_tables:
            available_tables = await schema_cache.get_tables(conn)
            if available_tables:   # Empty set means introspection failed; skip validation
                missing = required_tables - available_tables
                if missing:
                    logger.info(
                        f"[{request_id}] Skipping {db_name}: missing tables {missing}"
                    )
                    return {
                        "success": False,
                        "database_id": db_id,
                        "database_name": db_name,
                        "reason": "TABLE_NOT_FOUND",
                        "details": sorted(list(missing)),
                        "error": f"Table(s) not found: {', '.join(sorted(missing))}"
                    }

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
            result = await asyncio.wait_for(executor.execute(sql), timeout=timeout)
            
            exec_time_ms = int((time.monotonic() - t0) * 1000)
            
            rows = result.get("rows", [])
            # Inject source metadata
            for r in rows:
                r["_source_db"] = db_name

            return {
                "success": True,
                "database_id": db_id,
                "database_name": db_name,
                "rows": rows,
                "columns": result.get("columns", []),
                "execution_time_ms": exec_time_ms
            }

    except asyncio.TimeoutError:
        return {"success": False, "database_id": db_id, "database_name": db_name, "error": f"Query timed out (>{timeout}s)"}
    except Exception as e:
        logger.error(f"Execution error on {db_name}: {e}")
        return {"success": False, "database_id": db_id, "database_name": db_name, "error": str(e)}
    finally:
        await connector.disconnect()

async def run_parallel_sql(
    connections: List[DBConnection],
    sql: str,
    timeout: float = settings.GLOBAL_QUERY_TIMEOUT,
    request_id: str = "GENERIC"
) -> Dict[str, Any]:
    """Execute SQL across multiple connections in parallel and merge results."""
    t_start = time.monotonic()
    
    tasks = {
        asyncio.create_task(execute_sql_on_connection(c, sql, settings.DEFAULT_DB_TIMEOUT, request_id)): c
        for c in connections
    }
    
    done, pending = await asyncio.wait(
        tasks.keys(),
        timeout=timeout
    )
    
    for p_task in pending:
        p_task.cancel()
        
    successful_rows = []
    failed_sources = []
    
    for d_task in done:
        conn_obj = tasks[d_task]
        try:
            res = await d_task
            if res.get("success"):
                successful_rows.extend(res.get("rows", []))
            else:
                failed_sources.append({
                    "id": res.get("database_id"),
                    "database_name": res.get("database_name"),
                    "reason": res.get("reason", "EXECUTION_ERROR"),
                    "details": res.get("details"),
                    "error": res.get("error")
                })
        except Exception as e:
            failed_sources.append({
                "id": str(conn_obj.id),
                "database_name": conn_obj.connection_name or conn_obj.database_name,
                "reason": "EXECUTION_ERROR",
                "error": str(e)
            })

    for p_task in pending:
        conn_obj = tasks[p_task]
        failed_sources.append({
            "id": str(conn_obj.id),
            "database_name": conn_obj.connection_name or conn_obj.database_name,
            "reason": "TIMEOUT",
            "error": "Global Timeout"
        })

    merged_data = await _normalize_and_merge(successful_rows)
    execution_time_total = int((time.monotonic() - t_start) * 1000)
    
    return {
        "data": merged_data,
        "failed_sources": failed_sources,
        "row_count": len(merged_data),
        "execution_time_ms": execution_time_total,
    }
