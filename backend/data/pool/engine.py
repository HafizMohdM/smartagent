"""
Application Database Engine Configuration.
This handles the internal platform database (users, db_connections, saved_queries).
It does NOT handle the external databases that the AI agent connects to.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.config.settings import settings

# Baseline application DB engine (execution, CRUD)
engine = create_async_engine(
    settings.APP_DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Separate Vector DB engine (specifically for pgvector ANN searches)
# This prevents long-running HNSW scans from starving the execution pool
vector_engine = create_async_engine(
    settings.APP_DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=40,
)

vector_async_session_maker = async_sessionmaker(
    vector_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
