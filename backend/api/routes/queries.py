"""
Saved Queries routes.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.models.requests import SavedQueryCreateRequest
from backend.api.models.responses import SavedQueryResponse, StatusResponse
from backend.database.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.models.user import User
from backend.crud.query import save_query, list_saved_queries, delete_query

router = APIRouter(prefix="/api/queries", tags=["Saved Queries"])

@router.post("", response_model=SavedQueryResponse)
async def create_saved_query(
    request: SavedQueryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save an executed query."""
    query = await save_query(
        db=db,
        user_id=str(current_user.id),
        connection_id=request.connection_id,
        query_name=request.query_name,
        natural_language_query=request.natural_language_query,
        generated_sql=request.generated_sql,
        query_result_snapshot=request.query_result_snapshot,
        execution_time_ms=request.execution_time_ms,
        row_count=request.row_count
    )
    return query

@router.get("", response_model=List[SavedQueryResponse])
async def get_user_saved_queries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all saved queries for the current user."""
    queries = await list_saved_queries(db=db, user_id=str(current_user.id))
    return queries

@router.delete("/{query_id}", response_model=StatusResponse)
async def remove_saved_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a user's saved query."""
    deleted = await delete_query(db=db, query_id=query_id, user_id=str(current_user.id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved query not found"
        )
    return StatusResponse(status="success", message="Query deleted successfully")
