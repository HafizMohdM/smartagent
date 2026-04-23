"""
Chat Session & Message CRUD operations.
connection_id is now OPTIONAL — sessions may exist without a DB connection.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.models.chat_session import ChatSession
from backend.models.chat_message import ChatMessage


async def create_session(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
    connection_id: Optional[str] = None,
    session_name: Optional[str] = None,
) -> ChatSession:
    """
    Create a new chat session.
    connection_id is optional — pass None for sessions without a DB connection.
    """
    if not session_name:
        session_name = f"Chat - {datetime.now(timezone.utc).strftime('%b %d, %H:%M')}"

    session = ChatSession(
        user_id=user_id,
        tenant_id=tenant_id,
        connection_id=connection_id if connection_id else None,
        session_name=session_name,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_all_sessions_for_user(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    connection_id: Optional[str] = None,
) -> List[ChatSession]:
    """
    Get all chat sessions for a specific user within a tenant,
    optionally filtered by connection_id.
    """
    query = select(ChatSession).where(ChatSession.tenant_id == tenant_id).where(ChatSession.user_id == user_id)
    
    if connection_id:
        query = query.where(ChatSession.connection_id == connection_id)
    
    result = await db.execute(query.order_by(ChatSession.updated_at.desc()))
    return list(result.scalars().all())


async def get_all_sessions_for_connection(
    db: AsyncSession,
    tenant_id: str,
    connection_id: str,
) -> List[ChatSession]:
    """
    Get all chat sessions for a specific connection (kept for compatibility).
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.tenant_id == tenant_id)
        .where(ChatSession.connection_id == connection_id)
        .order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_session_by_id(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    user_id: str,
) -> Optional[ChatSession]:
    """
    Get a specific session, verifying tenant and user access.
    Returns session with messages eagerly loaded.
    """
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
        .where(ChatSession.tenant_id == tenant_id)
        .where(ChatSession.user_id == user_id)
    )
    return result.scalars().first()


async def get_session_messages(
    db: AsyncSession,
    session_id: str,
    limit: int = 200,
) -> List[ChatMessage]:
    """Return messages for a session ordered by created_at."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    message_text: str,
    generated_sql: Optional[str] = None,
    query_result_snapshot: Optional[dict] = None,
) -> ChatMessage:
    """Insert a new chat message."""
    # Sanitize complex types (date, datetime) for JSONB storage
    if query_result_snapshot:
        query_result_snapshot = json.loads(json.dumps(query_result_snapshot, default=str))

    msg = ChatMessage(
        session_id=session_id,
        role=role,
        message_text=message_text,
        generated_sql=generated_sql,
        query_result_snapshot=query_result_snapshot,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def touch_session(db: AsyncSession, session_id: str) -> None:
    """Update the session's updated_at timestamp."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalars().first()
    if session:
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def update_session_name(db: AsyncSession, session_id: str, new_name: str) -> bool:
    """Update a session's name. Verify existence first."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalars().first()
    if session:
        session.session_name = new_name
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True
    return False


async def delete_session(db: AsyncSession, session_id: str, tenant_id: str, user_id: str) -> bool:
    """Permanently delete a chat session and its messages."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .where(ChatSession.tenant_id == tenant_id)
        .where(ChatSession.user_id == user_id)
    )
    session = result.scalars().first()
    if session:
        await db.delete(session)
        await db.commit()
        return True
    return False
