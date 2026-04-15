"""
RBAC middleware and dependencies.
"""
from fastapi import Depends, HTTPException, status
from backend.models.user import User
from backend.security.jwt_auth import get_current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency — raises 403 if the user is not an admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def is_admin(user: User) -> bool:
    """Helper: returns True when the user has the admin role."""
    return user.role == "admin"
