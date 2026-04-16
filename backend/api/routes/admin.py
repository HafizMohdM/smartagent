"""
Admin-only approval endpoints.

GET  /api/admin/users/pending          → list pending user registrations
POST /api/admin/users/{id}/approve     → approve a user
POST /api/admin/users/{id}/reject      → reject a user
GET  /api/admin/connections/pending    → list pending connections
POST /api/admin/connections/{id}/approve
POST /api/admin/connections/{id}/reject
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.responses import UserResponse, DBConnectionResponse, StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.api.middleware.rbac import require_admin
from backend.models.user import User, UserStatus
from backend.models.db_connection import ConnectionStatus
from backend.security.user import list_pending_users, set_user_status
from backend.data.connector.crud import list_pending_connections, set_connection_status

router = APIRouter(prefix="/api/admin", tags=["Admin Approvals"])


# ── User approvals ────────────────────────────────────────────────

@router.get(
    "/users/pending",
    response_model=List[UserResponse],
    summary="List pending user registrations (Admin only)",
)
async def get_pending_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await list_pending_users(db=db, tenant_id=str(current_user.tenant_id))


@router.post(
    "/users/{user_id}/approve",
    response_model=UserResponse,
    summary="Approve a pending user (Admin only)",
)
async def approve_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await set_user_status(db, user_id, str(current_user.tenant_id), UserStatus.APPROVED)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post(
    "/users/{user_id}/reject",
    response_model=UserResponse,
    summary="Reject a pending user (Admin only)",
)
async def reject_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await set_user_status(db, user_id, str(current_user.tenant_id), UserStatus.REJECTED)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Connection approvals ──────────────────────────────────────────

@router.get(
    "/connections/pending",
    response_model=List[DBConnectionResponse],
    summary="List pending connection requests (Admin only)",
)
async def get_pending_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return await list_pending_connections(db=db, tenant_id=str(current_user.tenant_id))


@router.post(
    "/connections/{connection_id}/approve",
    response_model=DBConnectionResponse,
    summary="Approve a pending connection (Admin only)",
)
async def approve_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    conn = await set_connection_status(db, connection_id, str(current_user.tenant_id),
                                       ConnectionStatus.APPROVED)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.post(
    "/connections/{connection_id}/reject",
    response_model=DBConnectionResponse,
    summary="Reject a pending connection (Admin only)",
)
async def reject_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    conn = await set_connection_status(db, connection_id, str(current_user.tenant_id),
                                       ConnectionStatus.REJECTED)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn
