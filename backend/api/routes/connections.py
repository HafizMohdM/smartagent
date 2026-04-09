"""
Database connection routes.
RBAC:
  - GET  /api/connections  → all users (filtered by tenant; admin sees all)
  - POST /api/connections  → admin only
  - DELETE /api/connections/{id} → admin only
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.models.requests import ConnectionCreateRequest
from backend.api.models.responses import DBConnectionResponse, StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.api.middleware.rbac import require_admin, is_admin
from backend.models.user import User
from backend.data.connector.crud import create_connection, list_user_connections, delete_connection

router = APIRouter(prefix="/api/connections", tags=["Connections"])


@router.post("", response_model=DBConnectionResponse)
async def create_new_connection(
    request: ConnectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),   # admin only
):
    """Create a new database connection. Admin only."""
    conn = await create_connection(
        db=db,
        tenant_id=str(current_user.tenant_id),
        connection_name=request.connection_name,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        password=request.password,
        ssl_enabled=request.ssl_enabled,
        extra_params=request.extra_params,
    )
    return conn


@router.get("", response_model=List[DBConnectionResponse])
async def get_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get database connections.

    Admin  → all connections in the tenant.
    User   → same (connections are tenant-wide resources, not user-owned).
    Both are scoped to the tenant so cross-tenant access is impossible.
    """
    connections = await list_user_connections(db=db, tenant_id=str(current_user.tenant_id))
    return connections


@router.delete("/{connection_id}", response_model=StatusResponse)
async def remove_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),   # admin only
):
    """Delete a tenant connection. Admin only."""
    deleted = await delete_connection(
        db=db,
        connection_id=connection_id,
        tenant_id=str(current_user.tenant_id),
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
    return StatusResponse(status="success", message="Connection deleted successfully")
