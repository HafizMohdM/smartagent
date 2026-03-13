"""
Database connection routes.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.models.requests import ConnectionCreateRequest
from backend.api.models.responses import DBConnectionResponse, StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.models.user import User
from backend.data.connector.crud import create_connection, list_user_connections, delete_connection

router = APIRouter(prefix="/api/connections", tags=["Connections"])

@router.post("", response_model=DBConnectionResponse)
async def create_new_connection(
    request: ConnectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new database connection for the current user."""
    conn = await create_connection(
        db=db,
        user_id=str(current_user.id),
        connection_name=request.connection_name,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        password=request.password,
        ssl_enabled=request.ssl_enabled,
        extra_params=request.extra_params
    )
    return conn

@router.get("", response_model=List[DBConnectionResponse])
async def get_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all database connections belonging to the current user."""
    connections = await list_user_connections(db=db, user_id=str(current_user.id))
    return connections

@router.delete("/{connection_id}", response_model=StatusResponse)
async def remove_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a user connection."""
    deleted = await delete_connection(db=db, connection_id=connection_id, user_id=str(current_user.id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    return StatusResponse(status="success", message="Connection deleted successfully")
