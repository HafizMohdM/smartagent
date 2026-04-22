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
from backend.api.models.requests import SavedQueryCreateRequest, SavedQueryUpdateRequest, ExecuteQueryRequest
from backend.api.models.responses import SavedQueryResponse, StatusResponse, SQLDataContract
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.api.middleware.rbac import is_admin
from backend.models.user import User
from backend.data.executor.crud import save_query, list_saved_queries, delete_query, update_query, get_query
from backend.agent.utils.sql_parser import SQLParser
from backend.data.executor.orchestrator import run_parallel_sql
from backend.data.executor.generator import SQLGenerator

router = APIRouter(prefix="/api", tags=["Saved Queries"])


@router.post("/queries", response_model=SavedQueryResponse)
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



@router.get("/queries", response_model=List[SavedQueryResponse])
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


@router.delete("/queries/{query_id}", response_model=StatusResponse)
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

@router.patch("/queries/{query_id}", response_model=SavedQueryResponse)
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


@router.get("/queries/{query_id}/preview", response_model=SavedQueryResponse)
async def preview_saved_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Legacy execution route. Calls standardized execution logic.
    """
    q = await get_query(db, query_id, str(current_user.id))
    if not q:
        raise HTTPException(status_code=404, detail="Saved query not found")
    
    # Standardized execution
    from backend.models.db_connection import DBConnection
    execution_result = await run_parallel_sql(
        connections=q.connections,
        sql=q.generated_sql,
        trace_context={"request_id": f"preview_{q.id}"}
    )
    
    q.results = [execution_result]
    q.failed_sources = execution_result.get("failed_sources", [])
    q.execution_stats = {
        "time_ms": execution_result.get("execution_time_ms"),
        "total_rows": execution_result.get("row_count")
    }
        
    response = SavedQueryResponse.from_orm(q)
    response.results = getattr(q, "results", [])
    response.failed_sources = getattr(q, "failed_sources", [])
    response.execution_stats = getattr(q, "execution_stats", None)
    
    return response


@router.get("/queries/{query_id}", response_model=SavedQueryResponse)
@router.get("/saved-query/{query_id}", response_model=SavedQueryResponse)
async def get_saved_query_detail(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch Saved Query metadata.
    Requirement #4: Response MUST include id, title, generated_sql, connection_ids
    """
    q = await get_query(db, query_id, str(current_user.id))
    if not q:
        raise HTTPException(status_code=404, detail="Saved query not found")
    
    if not q.generated_sql:
        raise HTTPException(status_code=500, detail="Data corruption: generated_sql is missing for this query")

    return SavedQueryResponse.from_orm(q)


@router.post("/queries/execute", response_model=SQLDataContract)
@router.post("/execute-query", response_model=SQLDataContract)
async def execute_query_api(
    request: ExecuteQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Standardized execution API.
    Requirement #6: Request { sql, connection_ids } -> Response { rows, columns, meta }
    Requirement #9: Logging { query_id, sql, execution_status, execution_time }
    """
    from backend.data.connector.crud import get_connection
    from backend.models.db_connection import ConnectionStatus
    
    # 1. Resolve & Validate Connections
    validated_conns = []
    for cid in request.connection_ids:
        conn = await get_connection(db, cid, str(current_user.tenant_id))
        if not conn:
            raise HTTPException(status_code=404, detail=f"Connection {cid} not found")
        if conn.status != ConnectionStatus.APPROVED:
            raise HTTPException(status_code=403, detail=f"Connection {conn.connection_name} is not approved")
        validated_conns.append(conn)

    # 2. Execute
    try:
        result_dict = await run_parallel_sql(
            connections=validated_conns,
            sql=request.sql,
            trace_context={"user_id": str(current_user.id)}
        )
        
        # 3. Logging (Requirement #9)
        logger.info(
            f"[EXECUTION] query_id=raw, sql={request.sql[:100]}..., "
            f"status=success, time={result_dict.get('execution_time_ms')}ms"
        )
        
        # 4. Format into strict SQLDataContract
        res_meta = result_dict.get("meta", {})
        return SQLDataContract(
            rows=result_dict.get("rows", []),
            columns=result_dict.get("columns", []),
            meta={
                "row_count": res_meta.get("row_count", 0),
                "execution_time_ms": res_meta.get("execution_time_ms", 0),
                "version": "v1"
            }
        )
    except Exception as e:
        logger.error(f"[EXECUTION] query_id=raw, status=failed, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"Database execution failed: {str(e)}")
