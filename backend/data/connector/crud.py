"""
Database Connection CRUD operations.
"""
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.db_connection import DBConnection, ConnectionStatus
from backend.security.encryption import encrypt_password

logger = logging.getLogger(__name__)


async def get_connection(db: AsyncSession, connection_id: str, tenant_id: str) -> Optional[DBConnection]:
    result = await db.execute(
        select(DBConnection)
        .where(DBConnection.id == connection_id)
        .where(DBConnection.tenant_id == tenant_id)
    )
    return result.scalars().first()


async def list_user_connections(
    db: AsyncSession,
    tenant_id: str,
    approved_only: bool = False,
) -> List[DBConnection]:
    """List connections. approved_only=True filters to APPROVED status."""
    q = select(DBConnection).where(DBConnection.tenant_id == tenant_id)
    if approved_only:
        q = q.where(DBConnection.status == ConnectionStatus.APPROVED)
    result = await db.execute(q)
    return list(result.scalars().all())


async def list_pending_connections(db: AsyncSession, tenant_id: str) -> List[DBConnection]:
    result = await db.execute(
        select(DBConnection)
        .where(DBConnection.tenant_id == tenant_id)
        .where(DBConnection.status == ConnectionStatus.PENDING)
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
    extra_params: Optional[dict] = None,
    created_by: Optional[str] = None,
    is_admin_owned: bool = False,
    status: str = ConnectionStatus.PENDING,
) -> DBConnection:
    encrypted_password = encrypt_password(password)
    conn = DBConnection(
        tenant_id=tenant_id,
        connection_name=connection_name.strip(),
        db_type=db_type,
        host=host.strip(),
        port=port,
        database_name=database_name.strip(),
        username=username.strip(),
        encrypted_password=encrypted_password,
        ssl_enabled=ssl_enabled,
        extra_params=extra_params,
        created_by=created_by,
        is_admin_owned=is_admin_owned,
        status=status,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def delete_connection(db: AsyncSession, connection_id: str, tenant_id: str) -> bool:
    conn = await get_connection(db, connection_id, tenant_id)
    if conn:
        from backend.models.tenant_embedding import TenantEmbedding
        from sqlalchemy import delete
        
        # 1. Manually cleanup embeddings (since source_id is a String and doesn't auto-cascade)
        await db.execute(
            delete(TenantEmbedding)
            .where(TenantEmbedding.tenant_id == tenant_id)
            .where(TenantEmbedding.source_id == str(connection_id))
        )
        
        # 2. Delete the connection (TableMetadataStore will auto-cascade via FK)
        await db.delete(conn)
        await db.commit()
        return True
    return False


async def update_connection(
    db: AsyncSession,
    connection_id: str,
    tenant_id: str,
    connection_name: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    ssl_enabled: Optional[bool] = None,
) -> Optional[DBConnection]:
    conn = await get_connection(db, connection_id, tenant_id)
    if not conn:
        return None
    if connection_name is not None:
        conn.connection_name = connection_name.strip()
    if host is not None:
        conn.host = host.strip()
    if port is not None:
        conn.port = port
    if database_name is not None:
        conn.database_name = database_name.strip()
    if username is not None:
        conn.username = username.strip()
    if password is not None:
        conn.encrypted_password = encrypt_password(password)
    if ssl_enabled is not None:
        conn.ssl_enabled = ssl_enabled
    await db.commit()
    await db.refresh(conn)
    return conn


async def set_connection_status(
    db: AsyncSession,
    connection_id: str,
    tenant_id: str,
    new_status: str,
) -> Optional[DBConnection]:
    conn = await get_connection(db, connection_id, tenant_id)
    if not conn:
        return None
    conn.status = new_status
    await db.commit()
    await db.refresh(conn)
    return conn
