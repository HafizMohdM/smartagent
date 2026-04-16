"""
RBAC middleware and permission helpers.

Roles (lowest → highest privilege):
  user     → view approved connections, create (pending)
  manager  → user + edit own non-admin connections
  admin    → full access, approve/reject, bypass all checks
"""
from fastapi import Depends, HTTPException, status
from backend.models.user import User
from backend.models.db_connection import DBConnection, ConnectionStatus
from backend.security.jwt_auth import get_current_user


# ── Role helpers ──────────────────────────────────────────────────

def is_admin(user: User) -> bool:
    return user.role == "admin"

def is_manager(user: User) -> bool:
    return user.role in ("admin", "manager")


# ── FastAPI dependencies ──────────────────────────────────────────

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin privileges required")
    return current_user


async def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if not is_manager(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Manager or Admin privileges required")
    return current_user


# ── Connection permission checks ──────────────────────────────────

def can_edit_connection(user: User, conn: DBConnection) -> bool:
    """
    Admin  → always yes.
    Manager → only if they created it AND it is not admin-owned.
    User   → never.
    """
    if is_admin(user):
        return True
    if user.role == "manager":
        return (
            str(conn.created_by) == str(user.id)
            and not conn.is_admin_owned
        )
    return False


def can_delete_connection(user: User) -> bool:
    return is_admin(user)


def can_approve_connection(user: User) -> bool:
    return is_admin(user)


def assert_can_edit(user: User, conn: DBConnection) -> None:
    if not can_edit_connection(user, conn):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this connection.",
        )


def assert_can_delete(user: User) -> None:
    if not can_delete_connection(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete connections.",
        )


def assert_can_approve(user: User) -> None:
    if not can_approve_connection(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can approve or reject connections.",
        )
