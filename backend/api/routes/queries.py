"""
Saved Queries routes.
RBAC:
  - GET    /api/queries      → own queries (admin sees all in tenant)
  - POST   /api/queries      → any authenticated user
  - DELETE /api/queries/{id} → owner or admin
"""
import logging
from typing import List

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.models.requests import SavedQueryCreateRequest, SavedQueryUpdateRequest
from backend.api.models.responses import SavedQueryResponse, StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.api.middleware.rbac import is_admin
from backend.models.user import User
from backend.data.executor.crud import save_query, list_saved_queries, delete_query, update_query
from backend.agent.utils.sql_parser import SQLParser
from backend.data.executor.orchestrator import run_parallel_sql
from backend.data.executor.generator import SQLGenerator

router = APIRouter(prefix="/api/queries", tags=["Saved Queries"])


@router.post("", response_model=SavedQueryResponse)
async def create_saved_query(
    request: SavedQueryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save an executed query with multi-DB connection mapping."""
    if not request.title or not request.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    from backend.data.connector.crud import get_connection
    
    # Resolve connection mapping
    target_conn_ids = []
    
    # 1. From snapshot if multi-db
    multi_db = request.query_result_snapshot.get("multi_db") if isinstance(request.query_result_snapshot, dict) else None
    if multi_db and "results" in multi_db:
        # In multi-db, we can't always trust the request.connection_id to be set
        # We might have a list of connections in the snapshot
        for res in multi_db.get("results", []):
            cid = res.get("connection_id")
            if cid: target_conn_ids.append(str(cid))
    
    # 2. Add explicit connection_id if provided and not already in list
    if request.connection_id and str(request.connection_id) not in target_conn_ids:
        target_conn_ids.append(str(request.connection_id))

    if not target_conn_ids:
         raise HTTPException(status_code=400, detail="No database connections associated with this query")

    # Validate at least one exists
    conn = await get_connection(db, target_conn_ids[0], str(current_user.tenant_id))
    if not conn:
        raise HTTPException(status_code=404, detail="Primary database connection not found")

    try:
        saved_query_obj = await save_query(
            db=db,
            user_id=str(current_user.id),
            username=current_user.name or current_user.email,
            tenant_id=str(current_user.tenant_id),
            connection_id=target_conn_ids[0],
            database_name=conn.database_name,
            title=request.title,
            natural_language_query=request.natural_language_query,
            query=request.query,
            query_result_snapshot=request.query_result_snapshot,
            execution_time_ms=request.execution_time_ms,
            row_count=request.row_count,
            connection_ids=target_conn_ids
        )
        return saved_query_obj
    except ValueError as e:
        logger.warning(f"Failed to save query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )



@router.get("", response_model=List[SavedQueryResponse])
async def get_user_saved_queries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List saved queries.

    Admin → all queries for the user (same as user for now; extend to
            list_all_tenant_queries when needed).
    User  → only their own queries, filtered by user_id.
    """
    queries = await list_saved_queries(db=db, user_id=str(current_user.id))
    return queries


@router.delete("/{query_id}", response_model=StatusResponse)
async def remove_saved_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a saved query. Owner or admin may delete."""
    # Pass user_id for ownership check; the CRUD function handles the WHERE clause
    user_id_for_check = None if is_admin(current_user) else str(current_user.id)
    deleted = await delete_query(
        db=db,
        query_id=query_id,
        user_id=user_id_for_check or str(current_user.id),
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved query not found",
        )
    return StatusResponse(status="success", message="Query deleted successfully")

@router.patch("/{query_id}", response_model=SavedQueryResponse)
async def update_saved_query(
    query_id: str,
    request: SavedQueryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially update a saved query."""
    updated = await update_query(
        db=db,
        query_id=query_id,
        user_id=str(current_user.id),
        **request.dict(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved query not found or access denied",
        )
    return updated

@router.get("/{query_id}/preview", response_model=SavedQueryResponse)
async def preview_saved_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a saved query live against its associated databases.
    Implements 'Dynamic Execution' source-of-truth concept.
    """
    from backend.data.executor.crud import get_query
    q = await get_query(db, query_id, str(current_user.id))
    if not q:
        raise HTTPException(status_code=404, detail="Saved query not found")
    
    # 1. SQL Repair Logic (Concept: If source of truth is NOT executable, reconstruct it)
    if not SQLParser.is_executable(q.generated_sql):
        logger.info(f"Repairing non-executable SQL for query {q.id} ('{q.title}')")
        
        # 1.1 Hierarchical Repair - Scan history for a consistent fallback
        # If all successful executions used the same SQL, it's a safe repair.
        # If they used different SQL (Multi-DB scenario), we better use AI to regenerate a proper Multi-DB query.
        distinct_sqls = {e.sql for e in q.executions if e.sql and SQLParser.is_executable(e.sql) and e.status == "success"}
        
        if len(distinct_sqls) == 1:
            q.generated_sql = list(distinct_sqls)[0]
            logger.info(f"Found consistent historical fallback SQL for {q.id}")
            await db.commit()
        else:
            if len(distinct_sqls) > 1:
                logger.info(f"Inconsistent history for {q.id} ({len(distinct_sqls)} SQLs). Forcing AI repair.")
            
            # 1.2 Fallback to AI Generation
            generator = SQLGenerator()
            # Need schema for generation - use first connection
            if q.connections:
                from backend.data.connector.connector import DatabaseConnector
                from backend.security.encryption import decrypt_password
                
                conn = q.connections[0]
                connector = DatabaseConnector()
                try:
                    plaintext = decrypt_password(conn.encrypted_password)
                    await connector.connect(
                        host=conn.host, port=conn.port,
                        database=conn.database_name,
                        username=conn.username, password=plaintext,
                        connection_id=str(conn.id)
                    )
                    schema = connector.get_schema()
                    
                    new_sql_raw = await generator.generate(
                        user_query=q.query_text,
                        schema=schema,
                        connection_id=str(conn.id),
                        db_name=conn.connection_name or conn.database_name,
                        all_db_names=[c.connection_name for c in q.connections]
                    )
                    q.generated_sql = SQLParser.extract_sql(new_sql_raw) or new_sql_raw
                    # Save the repair permanently
                    await db.commit()
                    logger.info(f"Successfully repaired SQL via AI for {q.id}")
                except Exception as e:
                    logger.error(f"Failed to repair SQL for {q.id}: {e}")
                finally:
                    await connector.disconnect()

    # 2. Dynamic Execution
    if q.generated_sql and q.connections:
        try:
            execution_result = await run_parallel_sql(
                connections=q.connections,
                sql=q.generated_sql,
                request_id=f"preview_{q.id}"
            )
            
            # Map results to response
            q.results = execution_result.get("data", [])
            q.failed_sources = execution_result.get("failed_sources", [])
            q.execution_stats = {
                "time_ms": execution_result.get("execution_time_ms"),
                "total_rows": execution_result.get("row_count")
            }
        except Exception as e:
            logger.error(f"Dynamic execution failed for query {q.id}: {e}")
            # We still return the query object, but with empty results
            
    # 3. Explicitly construct response to ensure transient fields (results) are serialized
    # Note: Using from_orm(q) might skip dynamically assigned attributes that aren't columns.
    response = SavedQueryResponse.from_orm(q)
    response.results = getattr(q, "results", [])
    response.failed_sources = getattr(q, "failed_sources", [])
    response.execution_stats = getattr(q, "execution_stats", None)
    
    return response
