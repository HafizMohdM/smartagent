"""
JWT Authentication Middleware.
Validates Bearer tokens on protected endpoints and injects
user identity into the request state.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.settings import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Paths that do NOT require authentication
PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRY_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates JWT tokens on non-public routes."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths and CORS preflight requests
        if (
            request.method == "OPTIONS"
            or path in PUBLIC_PATHS
            or path.startswith("/docs")
            or path.startswith("/redoc")
        ):
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header.split(" ", 1)[1]
        payload = decode_access_token(token)

        # Inject user info into request state
        request.state.user_id = payload.get("sub", "unknown")
        request.state.session_id = payload.get("session_id", "")

        return await call_next(request)
