"""
Database connection routes with full RBAC + approval workflow.

Role matrix:
  ADMIN   → create (auto-approved), edit any, delete any, approve/reject
  MANAGER → create (pending), edit own non-admin connections
  USER    → create (pending), view approved only
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.requests import ConnectionCreateRequest, ConnectionUpdateRequest
from backend.api.models.responses import DBConnectionResponse, StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.api.middleware.rbac import (
    is_admin, require_admin,
    assert_can_edit, assert_can_delete, assert_can_approve,
)
from backend.models.user import User
from backend.models.db_connection import ConnectionStatus
from backend.data.connector.crud import (
    create_connection, list_user_connections, list_pending_connections,
    get_connection, delete_connection, update_connection, set_connection_status,
)

router = APIRouter(prefix="/api/connections", tags=["Connections"])


# ── List connections ──────────────────────────────────────────────

@router.get("", response_model=List[DBConnectionResponse])
async def get_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin/Manager → all connections in the tenant.
    User          → only APPROVED connections.
    """
    approved_only = not is_admin(current_user) and current_user.role != "manager"
    return await list_user_connections(db=db, tenant_id=str(current_user.tenant_id),
                                       approved_only=approved_only)


# ── Create connection ─────────────────────────────────────────────

@router.post("", response_model=DBConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_connection(
    request: ConnectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin   → connection is immediately APPROVED and marked admin-owned.
    Manager/User → connection is PENDING until an admin approves it.
    """
    admin = is_admin(current_user)
    conn_status = ConnectionStatus.APPROVED if admin else ConnectionStatus.PENDING
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
        created_by=str(current_user.id),
        is_admin_owned=admin,
        status=conn_status,
    )
    return conn


# ── Edit connection ───────────────────────────────────────────────

@router.patch("/{connection_id}", response_model=DBConnectionResponse)
async def edit_connection(
    connection_id: str,
    request: ConnectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin   → edit any connection.
    Manager → edit only own non-admin-owned connections.
    User    → forbidden.
    """
    conn = await get_connection(db, connection_id, str(current_user.tenant_id))
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    assert_can_edit(current_user, conn)

    updated = await update_connection(
        db=db,
        connection_id=connection_id,
        tenant_id=str(current_user.tenant_id),
        connection_name=request.connection_name,
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        password=request.password,
        ssl_enabled=request.ssl_enabled,
    )

    # Re-validate live connection if credentials changed
    if any(v is not None for v in [request.host, request.port, request.database_name,
                                    request.username, request.password]):
        from backend.data.connector.connector import DatabaseConnector
        from backend.security.encryption import decrypt_password
        try:
            connector = DatabaseConnector()
            await connector.connect(
                host=updated.host, port=updated.port, database=updated.database_name,
                username=updated.username, password=decrypt_password(updated.encrypted_password),
            )
            await connector.disconnect()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Connection updated but validation failed: {str(e)}")
    return updated


# ── Delete connection ─────────────────────────────────────────────

@router.delete("/{connection_id}", response_model=StatusResponse)
async def remove_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only."""
    assert_can_delete(current_user)
    deleted = await delete_connection(db=db, connection_id=connection_id,
                                      tenant_id=str(current_user.tenant_id))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return StatusResponse(status="success", message="Connection deleted successfully")


# ── Approval workflow ─────────────────────────────────────────────

@router.get("/pending", response_model=List[DBConnectionResponse])
async def get_pending_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin only — list all pending connections awaiting approval."""
    return await list_pending_connections(db=db, tenant_id=str(current_user.tenant_id))


@router.post("/{connection_id}/approve", response_model=DBConnectionResponse)
async def approve_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only — approve a pending connection."""
    assert_can_approve(current_user)
    conn = await set_connection_status(db, connection_id, str(current_user.tenant_id),
                                       ConnectionStatus.APPROVED)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return conn


@router.post("/{connection_id}/reject", response_model=DBConnectionResponse)
async def reject_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin only — reject a pending connection."""
    assert_can_approve(current_user)
    conn = await set_connection_status(db, connection_id, str(current_user.tenant_id),
                                       ConnectionStatus.REJECTED)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return conn
