"""
Chat routes — persistent chat sessions tied to database connections,
plus the original agent chat endpoint.
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.requests import ChatRequest, ChatMessageRequest
from backend.api.models.responses import (
    ChatResponse,
    ChatSessionResponse,
    ChatMessageItemResponse,
    ChatMessageSendResponse,
)
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.models.user import User
from backend.data.connector.crud import get_connection
from backend.memory.summary.chat import (
    get_or_create_session,
    get_session_with_messages,
    get_session_messages,
    create_message,
    touch_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])


# ── Persistent chat session endpoints ──────────────────────────────


@router.get(
    "/connections/{connection_id}/chat-session",
    response_model=ChatSessionResponse,
)
async def get_chat_session(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Load the chat session for a specific connection.
    If no session exists yet, one is created automatically.

    **Returns:** session metadata + full message history.
    """
    user_id = str(current_user.id)

    # Verify the connection belongs to this user
    conn = await get_connection(db, connection_id, user_id)
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found or access denied",
        )

    session = await get_session_with_messages(db, user_id, connection_id)

    return ChatSessionResponse(
        session_id=session.id,
        connection_id=session.connection_id,
        session_name=session.session_name,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageItemResponse(
                id=m.id,
                role=m.role,
                message_text=m.message_text,
                generated_sql=m.generated_sql,
                query_result_snapshot=m.query_result_snapshot,
                created_at=m.created_at,
            )
            for m in session.messages
        ],
    )


@router.post(
    "/chat-message",
    response_model=ChatMessageSendResponse,
)
async def send_chat_message(
    request: ChatMessageRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message within a persistent chat session.

    1. Get-or-create the chat session for (user, connection).
    2. Store the user message.
    3. Build conversation context from previous messages.
    4. Run the agent orchestrator.
    5. Store the agent response (with generated SQL & result snapshot).
    6. Update session timestamp.

    **Example request:**
    ```json
    {
        "connection_id": "uuid-of-connection",
        "message": "Show me top 10 customers by revenue"
    }
    ```
    """
    user_id = str(current_user.id)
    connection_id = request.connection_id

    # Verify the connection belongs to this user
    conn = await get_connection(db, connection_id, user_id)
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found or access denied",
        )

    # 1. Get or create session
    session = await get_or_create_session(db, user_id, connection_id)
    session_id_str = str(session.id)

    # 2. Store user message
    user_msg = await create_message(
        db=db,
        session_id=session_id_str,
        role="user",
        message_text=request.message,
    )

    # 3. Build conversation history for agent context
    previous_messages = await get_session_messages(db, session_id_str)
    history = [
        {"role": m.role, "content": m.message_text}
        for m in previous_messages
    ]

    # 4. Run agent
    try:
        orchestrator = req.app.state.orchestrator

        # Create a temporary runtime session for the orchestrator
        session_mgr = req.app.state.session_manager
        runtime_session_id = await session_mgr.create_session(user_id)

        result = await orchestrator.run(
            query=request.message,
            session_id=runtime_session_id,
            history=history,
        )

        # Clean up the temporary runtime session
        await session_mgr.delete_session(runtime_session_id)

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent processing failed: {str(e)}",
        )

    # 5. Store agent response
    agent_msg = await create_message(
        db=db,
        session_id=session_id_str,
        role="agent",
        message_text=result.get("response", ""),
        generated_sql=result.get("generated_sql"),
        query_result_snapshot=result.get("tool_result"),
    )

    # 6. Touch session timestamp
    await touch_session(db, session_id_str)

    return ChatMessageSendResponse(
        user_message=ChatMessageItemResponse(
            id=user_msg.id,
            role=user_msg.role,
            message_text=user_msg.message_text,
            generated_sql=user_msg.generated_sql,
            query_result_snapshot=user_msg.query_result_snapshot,
            created_at=user_msg.created_at,
        ),
        agent_message=ChatMessageItemResponse(
            id=agent_msg.id,
            role=agent_msg.role,
            message_text=agent_msg.message_text,
            generated_sql=agent_msg.generated_sql,
            query_result_snapshot=agent_msg.query_result_snapshot,
            created_at=agent_msg.created_at,
        ),
        tool_used=result.get("tool_used"),
        metadata={"plan": result.get("plan", {})},
    )


# ── Legacy agent chat endpoint (unchanged) ─────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Send a natural-language message to the AI agent (stateless / Redis session).

    This is the original endpoint. For persistent chat history, use
    ``POST /api/chat-message`` instead.
    """
    session_id = request.session_id

    session_mgr = req.app.state.session_manager
    session = await session_mgr.get_session(session_id)
    
    # If session doesn't exist but we have a valid user from the token, auto-create it
    if session is None:
        user_id = getattr(req.state, "user_id", "unknown")
        logger.info(f"Auto-creating missing session {session_id} for user {user_id}")
        # We manually use the requested session_id to match the frontend expectation
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "connections": {},
            "metadata": {"auto_created": True},
        }
        await session_mgr._store_session(session_id, session_data)
        session = session_data

    try:
        orchestrator = req.app.state.orchestrator
        result = await orchestrator.run(
            query=request.message,
            session_id=session_id,
        )

        return ChatResponse(
            response=result["response"],
            tool_used=result.get("tool_used"),
            metadata={"plan": result.get("plan", {})},
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}",
        )


@router.get("/chat/history")
async def get_chat_history(session_id: str, req: Request, limit: int = 50):
    """
    Retrieve conversation history for a Redis/in-memory session.

    For persistent history, use ``GET /api/connections/{id}/chat-session``.
    """
    session_mgr = req.app.state.session_manager
    history = await session_mgr.get_history(session_id, limit=limit)
    
    # If history is empty, it might be a new auto-created session or truly empty
    return {"session_id": session_id, "messages": history, "count": len(history)}
