"""
Database Connection CRUD operations.
"""
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.db_connection import DBConnection
from backend.security.encryption import encrypt_password

logger = logging.getLogger(__name__)

async def get_connection(db: AsyncSession, connection_id: str, tenant_id: str) -> Optional[DBConnection]:
    """Retrieve a specific connection if it belongs to the tenant."""
    result = await db.execute(
        select(DBConnection)
        .where(DBConnection.id == connection_id)
        .where(DBConnection.tenant_id == tenant_id)
    )
    return result.scalars().first()

async def list_user_connections(db: AsyncSession, tenant_id: str) -> List[DBConnection]:
    """Retrieve all connections for a specific tenant."""
    result = await db.execute(
        select(DBConnection).where(DBConnection.tenant_id == tenant_id)
    )
    return list(result.scalars().all())

async def create_connection(
    db: AsyncSession, 
    tenant_id: str, 
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
    """Create a new database connection for a tenant."""
    encrypted_password = encrypt_password(password)
    
    conn = DBConnection(
        tenant_id=tenant_id,
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

async def delete_connection(db: AsyncSession, connection_id: str, tenant_id: str) -> bool:
    """Delete a tenant's database connection."""
    conn = await get_connection(db, connection_id, tenant_id)
    if conn:
        await db.delete(conn)
        await db.commit()
        return True
    return False
