"""
Authentication routes — registration, login, logout, and profile.

Hardcoded quick-login credentials:
  admin / admin123  →  admin@admin.local  (role: admin)
  user  / user123   →  user@user.local    (role: user)
"""
import logging
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.models.requests import LoginRequest, UserRegisterRequest
from backend.api.models.responses import LoginResponse, StatusResponse, UserResponse
from backend.security.jwt_auth import create_access_token, get_current_user
from backend.security.hashing import hash_password, verify_password
from backend.config.settings import settings
from backend.data.pool.session import get_db
from backend.security.user import get_user_by_email, create_user
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# ── Hardcoded shortcut credentials ────────────────────────────────────────────
# Maps username → (actual email used in DB, plaintext password for verification)
HARDCODED_USERS = {
    "admin": ("admin@admin.local", "admin123"),
    "user":  ("user@user.local",   "user123"),
}


def _resolve_email(email_or_username: str) -> str:
    """If the caller used a shorthand username, resolve it to its DB email."""
    stripped = email_or_username.strip().lower()
    if stripped in HARDCODED_USERS:
        return HARDCODED_USERS[stripped][0]
    return email_or_username


@router.post("/register", response_model=UserResponse)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    existing_user = await get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = hash_password(request.password)
    user = await create_user(
        db=db,
        email=request.email,
        password_hash=hashed_pwd,
        name=request.name,
        phone_number=request.phone_number,
        role="user",
    )
    logger.info(f"New user registered: {user.email}")
    return user


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return a JWT access token.

    Accepts either a real email address or a shorthand username
    (admin / user) for the hardcoded demo accounts.
    """
    resolved_email = _resolve_email(request.email)
    user = await get_user_by_email(db, resolved_email)

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Use session manager from app state
    session_mgr = req.app.state.session_manager
    session_id = await session_mgr.create_session(user_id=str(user.id))

    # Generate JWT – include role so frontend can act immediately
    token = create_access_token(
        data={
            "sub": user.email,
            "session_id": session_id,
            "user_id": str(user.id),
            "role": user.role,
        },
        expires_delta=timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    )

    logger.info(f"User '{user.email}' logged in (role={user.role}). Session: {session_id}")
    return LoginResponse(
        access_token=token,
        session_id=session_id,
        role=user.role,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )


@router.post("/logout", response_model=StatusResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """Log out the current user."""
    return StatusResponse(status="success", message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user's profile including role."""
    return current_user
