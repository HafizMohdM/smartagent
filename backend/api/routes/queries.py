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

router = APIRouter(prefix="/api/queries", tags=["Saved Queries"])


@router.post("", response_model=SavedQueryResponse)
async def create_saved_query(
    request: SavedQueryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save an executed query."""
    if not request.title or not request.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    from backend.data.connector.crud import get_connection
    conn = await get_connection(db, request.connection_id, str(current_user.tenant_id))
    if not conn:
        raise HTTPException(status_code=404, detail="Database connection not found")

    try:
        saved_query_obj = await save_query(
            db=db,
            user_id=str(current_user.id),
            username=current_user.name or current_user.email,
            tenant_id=str(current_user.tenant_id),
            connection_id=request.connection_id,
            database_name=conn.database_name,
            title=request.title,
            natural_language_query=request.natural_language_query,
            query=request.query,
            query_result_snapshot=request.query_result_snapshot,
            execution_time_ms=request.execution_time_ms,
            row_count=request.row_count,
        )
        return saved_query_obj
    except ValueError as e:
        logger.warning(f"Failed to save query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid SQL found in response"
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
    """Execute a saved query with LIMIT 100 for a fresh preview/schema extraction."""
    from sqlalchemy.future import select
    from backend.models.saved_query import SavedQuery
    from backend.models.db_connection import DBConnection
    from backend.data.executor import executor
    from backend.data.connector.connector import DatabaseConnector
    from backend.security.encryption import decrypt_password

    # 1. Fetch query (with tenant/user isolation)
    stmt = select(SavedQuery).where(
        SavedQuery.id == query_id,
        SavedQuery.tenant_id == str(current_user.tenant_id)
    )
    if not is_admin(current_user):
        stmt = stmt.where(SavedQuery.user_id == str(current_user.id))
        
    result = await db.execute(stmt)
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(status_code=404, detail="Saved query not found")

    # 2. Fetch connection
    conn_result = await db.execute(select(DBConnection).where(DBConnection.id == query.connection_id))
    conn = conn_result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Database connection not found")

    # 3. Decrypt and Execute
    try:
        pw = decrypt_password(conn.encrypted_password)
        
        # Requirement 1: SQL Extraction and Validation
        pure_sql = SQLParser.extract_sql(query.query) or query.query.strip()
        if not pure_sql or not SQLParser.is_valid_query(pure_sql):
            logger.error(f"Invalid query attempted for preview: {pure_sql}")
            raise HTTPException(status_code=400, detail="Invalid query. Please select a valid saved query.")

        connector = DatabaseConnector()
        await connector.connect(
            host=conn.host, port=conn.port, database=conn.database_name,
            username=conn.username, password=pw
        )
        
        # Requirement 2: Safe Execution with subquery wrap
        # Strip trailing semicolons from the inner query
        inner_sql = pure_sql.rstrip(';').strip()
        sql_with_limit = f"SELECT * FROM ({inner_sql}) AS subquery_preview LIMIT 100"
        
        logger.info(f"Executing preview SQL: {sql_with_limit}")
        
        sql_executor = executor.SQLExecutor(connector)
        exec_result = await sql_executor.execute(sql_with_limit)
        
        # Return as a SavedQueryResponse (reusing the model for columns/rows)
        return SavedQueryResponse(
            id=query.id,
            connection_id=query.connection_id,
            tenant_id=query.tenant_id,
            database_name=query.database_name,
            username=query.username,
            title=query.title,
            natural_language_query=query.natural_language_query,
            query=query.query,
            query_result_snapshot=exec_result, # Fresh snapshot
            execution_time_ms=exec_result["execution_time_ms"],
            row_count=exec_result["row_count"],
            created_at=query.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute preview query: {e}", exc_info=True)
        # Requirement 3: Clean error message
        raise HTTPException(status_code=400, detail="Failed to execute query. Please verify query format.")
    finally:
        if 'connector' in locals():
            await connector.disconnect()
