"""
User CRUD operations.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.user import User
from backend.security.hashing import hash_password

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Retrieve a user by their email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Retrieve a user by their ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()

async def create_user(db: AsyncSession, email: str, password_hash: str, name: Optional[str] = None, phone_number: Optional[str] = None) -> User:
    """Create a new user in the database."""
    user = User(
        email=email,
        password_hash=password_hash,
        name=name,
        phone_number=phone_number
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
