"""
Authentication routes.

Login rules:
  - ADMIN  → can always login (status bypassed)
  - USER / MANAGER → must have status=APPROVED and is_active=True

Registration:
  - Any role except admin → status=PENDING, is_active=False
  - Admin is seeded only, never self-registered
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
from backend.models.user import User, UserStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Admin shortcut only — user/manager must register and be approved
ADMIN_SHORTCUT = {"admin": ("admin@admin.local", "admin123")}


def _resolve_email(email_or_username: str) -> str:
    stripped = email_or_username.strip().lower()
    if stripped in ADMIN_SHORTCUT:
        return ADMIN_SHORTCUT[stripped][0]
    return email_or_username


@router.post(
    "/register",
    response_model=UserResponse,
    summary="Register a new user (USER or MANAGER)",
    description=(
        "Creates a new account with status=PENDING. "
        "The account cannot be used until an admin approves it. "
        "Role must be 'user' or 'manager' — admin accounts are seeded only."
    ),
)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    if request.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot self-register as admin.")

    existing = await get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Resolve the default tenant — every self-registered user joins the single tenant
    from backend.models.tenant import Tenant
    from sqlalchemy.future import select as sa_select
    result = await db.execute(sa_select(Tenant).limit(1))
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=500, detail="No tenant configured. Contact an administrator.")

    hashed = hash_password(request.password)
    user = await create_user(
        db=db,
        email=request.email,
        password_hash=hashed,
        name=request.name,
        phone_number=getattr(request, "phone_number", None),
        tenant_id=str(tenant.id),
        role=request.role or "user",
        status=UserStatus.PENDING,
        is_active=False,
    )
    logger.info(f"New user registered (pending): {user.email} role={user.role}")
    return user


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description=(
        "ADMIN can always login. "
        "USER/MANAGER can only login if their account has been approved by an admin."
    ),
)
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db)):
    resolved_email = _resolve_email(request.email)
    user = await get_user_by_email(db, resolved_email)

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Non-admin users must be approved
    if user.role != "admin":
        if user.status != UserStatus.APPROVED:
            msg = {
                UserStatus.PENDING:  "Your account is pending admin approval.",
                UserStatus.REJECTED: "Your account has been rejected. Contact an administrator.",
            }.get(user.status, "Account not approved.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Account is inactive.")

    session_mgr = req.app.state.session_manager
    session_id = await session_mgr.create_session(user_id=str(user.id))

    token = create_access_token(
        data={"sub": user.email, "session_id": session_id,
              "user_id": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    )

    logger.info(f"Login: {user.email} role={user.role}")
    return LoginResponse(
        success=True,
        token=token,
        access_token=token,
        session_id=session_id,
        role=user.role,
        user={"id": str(user.id), "email": user.email, "role": user.role},
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )


@router.post("/logout", response_model=StatusResponse)
async def logout(current_user: User = Depends(get_current_user)):
    return StatusResponse(status="success", message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
