"""
Application Database Engine Configuration.
This handles the internal platform database (users, db_connections, saved_queries).
It does NOT handle the external databases that the AI agent connects to.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.config.settings import settings

# Create the async engine for the application database
engine = create_async_engine(
    settings.APP_DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# Create a customized async session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
