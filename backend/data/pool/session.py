"""
Database session dependency.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from backend.data.pool.engine import async_session_maker

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting async sessions."""
    async with async_session_maker() as session:
        yield session
