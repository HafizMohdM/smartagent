"""
User CRUD operations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.user import User, UserStatus


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    name: Optional[str] = None,
    phone_number: Optional[str] = None,
    tenant_id: Optional[str] = None,
    role: str = "user",
    status: str = UserStatus.PENDING,
    is_active: bool = False,
) -> User:
    kwargs: dict = dict(
        email=email,
        password_hash=password_hash,
        name=name,
        phone_number=phone_number,
        role=role,
        status=status,
        is_active=is_active,
    )
    if tenant_id:
        kwargs["tenant_id"] = tenant_id
    user = User(**kwargs)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_all_users(db: AsyncSession, tenant_id: str) -> List[User]:
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def list_pending_users(db: AsyncSession, tenant_id: str) -> List[User]:
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id)
        .where(User.status == UserStatus.PENDING)
        .order_by(User.created_at)
    )
    return list(result.scalars().all())


async def set_user_status(
    db: AsyncSession, user_id: str, tenant_id: str, new_status: str
) -> Optional[User]:
    user = await get_user_by_id(db, user_id)
    if not user or str(user.tenant_id) != tenant_id:
        return None
    user.status = new_status
    user.is_active = (new_status == UserStatus.APPROVED)
    await db.commit()
    await db.refresh(user)
    return user
