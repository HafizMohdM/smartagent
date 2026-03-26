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
from fastapi.responses import JSONResponse
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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # Add fallback for user_id/email if 'sub' is missing (Django tokens)
        if "sub" not in payload:
            payload["sub"] = payload.get("user_id") or payload.get("email") or "unknown"
        return payload
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

        try:
            # Extract Bearer token
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

            token = auth_header.split(" ", 1)[1]
            payload = decode_access_token(token)

            # Inject user info into request state
            # Ensure user_id is a string and handle Django 'user_id' claim
            request.state.user_id = str(payload.get("sub") or payload.get("user_id") or "unknown")
            
            # Use session_id from JWT, or from X-Session-ID header (for SSO/Iframe)
            request.state.session_id = payload.get("session_id") or request.headers.get("X-Session-ID") or ""
            
            return await call_next(request)

        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
        except Exception as e:
            logger.exception("Unexpected error in auth middleware")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Internal auth error: {str(e)}"},
            )
