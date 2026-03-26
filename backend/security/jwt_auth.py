"""
JWT Authentication module.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError as JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config.settings import settings
from backend.data.pool.session import get_db
from backend.security.user import get_user_by_email
from backend.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """Dependency to retrieve the current logged-in user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # Django SimpleJWT uses 'user_id', FastAPI templates often use 'sub'
        email: str = payload.get("sub") or payload.get("email")
        user_id: str = payload.get("user_id") # Django primary key
        
        if email is None and user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
        
    # 1. Try to find user by email
    if email:
        user = await get_user_by_email(db, email=email)
        if user:
            return user
            
    # 2. Try to find user by user_id (if we mapped it to our ID field)
    if user_id:
        user = await get_user_by_id(db, user_id=str(user_id))
        if user:
            return user

    # 3. Fallback for Iframe/HRMS Integration: 
    # If the token is valid (it is, because we passed jwt.decode), but the user 
    # isn't in our local DB, return a temporary mock User object.
    # This allows the AI Agent to function as a stateless assistant for external apps.
    return User(
        id=str(user_id or "external"),
        email=email or f"user_{user_id}@external.com",
        name=payload.get("name", "HRMS User"),
        is_active=True
    )
