"""
Chat Session & Message CRUD operations.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.models.chat_session import ChatSession
from backend.models.chat_message import ChatMessage


async def get_or_create_session(
    db: AsyncSession,
    user_id: str,
    connection_id: str,
) -> ChatSession:
    """
    Return the existing chat session for (user_id, connection_id),
    or create a new one if none exists.
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .where(ChatSession.connection_id == connection_id)
    )
    session = result.scalars().first()

    if session is None:
        session = ChatSession(
            user_id=user_id,
            connection_id=connection_id,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return session


async def get_session_with_messages(
    db: AsyncSession,
    user_id: str,
    connection_id: str,
) -> ChatSession:
    """
    Get-or-create the session, then eagerly load its messages.
    """
    session = await get_or_create_session(db, user_id, connection_id)

    # Reload with messages eager-loaded
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session.id)
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
