"""
Database Connection CRUD operations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.db_connection import DBConnection
from backend.security.encryption import encrypt_password

async def get_connection(db: AsyncSession, connection_id: str, user_id: str) -> Optional[DBConnection]:
    """Retrieve a specific connection if it belongs to the user."""
    result = await db.execute(
        select(DBConnection)
        .where(DBConnection.id == connection_id)
        .where(DBConnection.user_id == user_id)
    )
    return result.scalars().first()

async def list_user_connections(db: AsyncSession, user_id: str) -> List[DBConnection]:
    """Retrieve all connections for a specific user."""
    result = await db.execute(
        select(DBConnection).where(DBConnection.user_id == user_id)
    )
    return list(result.scalars().all())

async def create_connection(
    db: AsyncSession, 
    user_id: str, 
    connection_name: str,
    db_type: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    ssl_enabled: bool = False,
    extra_params: Optional[dict] = None
) -> DBConnection:
    """Create a new database connection for a user."""
    encrypted_password = encrypt_password(password)
    
    conn = DBConnection(
        user_id=user_id,
        connection_name=connection_name,
        db_type=db_type,
        host=host,
        port=port,
        database_name=database_name,
        username=username,
        encrypted_password=encrypted_password,
        ssl_enabled=ssl_enabled,
        extra_params=extra_params
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn

async def delete_connection(db: AsyncSession, connection_id: str, user_id: str) -> bool:
    """Delete a user's database connection."""
    conn = await get_connection(db, connection_id, user_id)
    if conn:
        await db.delete(conn)
        await db.commit()
        return True
    return False
