"""
Saved Query CRUD operations.
"""
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.models.query import Query, QueryExecution
from backend.agent.utils.sql_parser import SQLParser

async def list_saved_queries(db: AsyncSession, user_id: str) -> List[Query]:
    """Retrieve all saved queries for a specific user."""
    result = await db.execute(
        select(Query)
        .options(selectinload(Query.executions), selectinload(Query.connections))
        .where(Query.user_id == user_id)
    )
    return list(result.scalars().all())

async def save_query(
    db: AsyncSession,
    user_id: str,
    username: str,
    tenant_id: str,
    connection_id: str, # For single DB
    database_name: str,
    title: str,
    natural_language_query: str,
    query: str,
    query_result_snapshot: Optional[Any] = None,
    execution_time_ms: Optional[int] = None,
    row_count: Optional[int] = None,
    connection_ids: Optional[List[str]] = None # For multi DB
) -> Query:
    from backend.models.db_connection import DBConnection

    # 1. SQL is the absolute source of truth. It MUST be provided in the request.
    # We no longer allow saving without a valid SQL definition.
    extracted_sql = SQLParser.extract_sql(query)
    
    if not extracted_sql or not extracted_sql.strip():
        raise ValueError("A valid SQL query is required to save.")

    final_sql = extracted_sql

    # 1. Establish connections association (Fetch first to avoid async lazy loading)
    target_ids = connection_ids if connection_ids else ([connection_id] if connection_id else [])
    connections = []
    if target_ids:
        conn_result = await db.execute(
            select(DBConnection).where(DBConnection.id.in_(target_ids), DBConnection.tenant_id == tenant_id)
        )
        connections = list(conn_result.scalars().all())

    # 2. Create Query object (Pass connections in constructor)
    q = Query(
        user_id=user_id,
        tenant_id=tenant_id,
        title=title,
        query_text=natural_language_query,
        generated_sql=final_sql, # [NEW] Persistent SQL definition
        username=username,
        connections=connections
    )
    db.add(q)
    await db.flush()

    # 2. Add executions (LOG ONLY - No result storage)
    executions_to_insert = []
    
    multi_db = query_result_snapshot.get("multi_db") if isinstance(query_result_snapshot, dict) else None
    if multi_db and "results" in multi_db:
        # Multi DB Logging
        for row in multi_db["results"]:
            db_name = row.get("database")
            sql_used = row.get("sql")
            status = "failed" if row.get("error") else ("success" if sql_used else "skipped")
            
            q_exec = QueryExecution(
                query_id=q.id,
                database_name=db_name,
                sql=sql_used,
                status=status,
                # result_json REMOVED
                error=row.get("error"),
                execution_time_ms=row.get("execution_ms"),
                row_count=row.get("row_count")
            )
            executions_to_insert.append(q_exec)
    else:
        # Single DB Logging
        status = "failed" if isinstance(query_result_snapshot, dict) and query_result_snapshot.get("error") else "success"
        
        q_exec = QueryExecution(
            query_id=q.id,
            database_name=database_name or "unknown",
            sql=final_sql,
            status=status,
            # result_json REMOVED
            error=query_result_snapshot.get("error") if isinstance(query_result_snapshot, dict) else None,
            execution_time_ms=execution_time_ms,
            row_count=row_count
        )
        executions_to_insert.append(q_exec)

    for e in executions_to_insert:
        db.add(e)
        
    await db.commit()
    await db.refresh(q)
    result = await db.execute(select(Query).options(selectinload(Query.executions), selectinload(Query.connections)).where(Query.id == q.id))
    return result.scalars().first()


async def get_query(db: AsyncSession, query_id: str, user_id: str) -> Optional[Query]:
    """Retrieve a specific saved query if it belongs to the user."""
    result = await db.execute(
        select(Query)
        .options(selectinload(Query.executions), selectinload(Query.connections))
        .where(Query.id == query_id)
        .where(Query.user_id == user_id)
    )
    return result.scalars().first()

async def delete_query(db: AsyncSession, query_id: str, user_id: str) -> bool:
    """Delete a user's saved query."""
    query_obj = await get_query(db, query_id, user_id)
    if query_obj:
        await db.delete(query_obj)
        await db.commit()
        return True
    return False


async def update_query(
    db: AsyncSession,
    query_id: str,
    user_id: str,
    **updates
) -> Optional[Query]:
    """Partially update a saved query. (Metadata only, executions update is unsupported here)"""
    query_obj = await get_query(db, query_id, user_id)
    if not query_obj:
        return None
    
    for key, value in updates.items():
        if hasattr(query_obj, key) and value is not None:
            # Not supporting direct SQL updates easily now as SQL runs per Execution
            # but we can update the title
            if key == "query_text" or key == "title":
                setattr(query_obj, key, value)
    
    await db.commit()
    await db.refresh(query_obj)
    return query_obj
