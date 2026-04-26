"""
Chat routes — global persistent chat sessions with optional database context.

Key changes from previous version:
  - Sessions are NO LONGER tied to a specific connection at creation.
  - GET /api/chat-sessions  → list all sessions for the current user.
  - POST /api/chat-message  → connection_id is OPTIONAL.
      * If provided → validate, connect DB tool, run agent with DB context.
      * If absent   → run agent without DB tool (non-DB AI responses only).
  - Legacy /api/chat (stateless Redis) endpoint kept for reference.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.responses import (
    ChatResponse,
    ChatSessionResponse,
    ChatSessionMetaResponse,
    ChatMessageItemResponse,
    ChatMessageSendResponse,
)
from backend.api.models.requests import ChatRequest, ChatMessageRequest, ChatSessionRenameRequest
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.models.user import User
from backend.data.connector.crud import get_connection, list_user_connections
from backend.memory.summary.chat import (
    create_session,
    get_all_sessions_for_user,
    get_session_by_id,
    get_session_messages,
    create_message,
    touch_session,
    update_session_name,
)
from backend.security.encryption import decrypt_password

from backend.agent.tools.base import ToolResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])

def result_to_tool_result(res: Dict[str, Any]) -> ToolResult:
    """Helper to convert a strict contract dict to a ToolResult object."""
    return ToolResult(
        success=True,
        data=res,
        metadata=res.get("meta", {})
    )


# ── Global chat session list ───────────────────────────────────────────────────


@router.get(
    "/chat-sessions",
    response_model=List[ChatSessionMetaResponse],
)
async def list_chat_sessions(
    connection_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all chat sessions for the current user.
    If connection_id is provided, filters for that specific database.
    """
    tenant_id = str(current_user.tenant_id)
    user_id = str(current_user.id)

    # Security: Validate connection ownership if provided
    if connection_id:
        from backend.data.connector.crud import get_connection
        conn = await get_connection(db, connection_id, tenant_id)
        if not conn:
            # We don't return 404 to avoid leaking valid connection IDs
            return []

    sessions = await get_all_sessions_for_user(db, tenant_id, user_id, connection_id)
    return [
        ChatSessionMetaResponse(
            session_id=s.id,
            connection_id=s.connection_id,
            session_name=s.session_name,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


# ── Session detail ─────────────────────────────────────────────────────────────


@router.get(
    "/chat-sessions/{session_id}",
    response_model=ChatSessionResponse,
)
async def get_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load a specific chat session with its full message history."""
    tenant_id = str(current_user.tenant_id)
    user_id = str(current_user.id)
    session = await get_session_by_id(db, session_id, tenant_id, user_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )

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


@router.patch("/chat-sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    request: ChatSessionRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename an existing chat session."""
    tenant_id = str(current_user.tenant_id)
    user_id = str(current_user.id)
    
    # Verify ownership
    session = await get_session_by_id(db, session_id, tenant_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
        
    success = await update_session_name(db, session_id, request.session_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update session name")
        
    return {"status": "success", "session_id": session_id, "new_name": request.session_name}


@router.delete("/chat-sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session."""
    tenant_id = str(current_user.tenant_id)
    user_id = str(current_user.id)
    
    from backend.memory.summary.chat import delete_session
    success = await delete_session(db, session_id, tenant_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or access denied")
        
    return {"status": "success", "session_id": session_id}


# ── Send message ───────────────────────────────────────────────────────────────


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
    Send a message in a global chat session.

    connection_id behaviour:
      - Provided  → validate ownership, connect DB tool, agent has full DB context.
      - Not given → agent runs without DB tool; DB queries will return a
                    "No database connected" message.
    """
    user_id = str(current_user.id)
    tenant_id = str(current_user.tenant_id)
    connection_id = request.connection_id

    # ── Resolve connection IDs ─────────────────────────────────────────────────
    # Support both single connection_id and multi connection_ids
    raw_ids: List[str] = []
    if request.connection_ids:
        raw_ids = [cid.strip() for cid in request.connection_ids if cid.strip()]
    elif connection_id:
        raw_ids = [connection_id]

    if not raw_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No database connection specified."
        )

    # Validate all connections belong to this tenant
    from backend.data.connector.crud import get_connection
    validated_conns = []
    for cid in raw_ids:
        conn = await get_connection(db, cid, tenant_id)
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied or connection not found: {cid}",
            )
        # Only APPROVED connections can be used in chat
        from backend.models.db_connection import ConnectionStatus
        if conn.status != ConnectionStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Connection '{conn.connection_name}' is not approved yet. "
                       f"Current status: {conn.status}.",
            )
        validated_conns.append(conn)

    # Use the first connection_id for session tracking (backward compat)
    primary_conn = validated_conns[0]
    connection_id = str(primary_conn.id)

    try:
        plaintext_password = decrypt_password(primary_conn.encrypted_password)
    except Exception as e:
        logger.error(f"Credential decryption failed for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt database credentials.",
        )

    # ── Get or create session ──────────────────────────────────────────────────
    if request.session_id:
        session = await get_session_by_id(db, request.session_id, tenant_id, user_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            )
    else:
        session = await create_session(
            db, user_id, tenant_id, connection_id=connection_id
        )

    session_id_str = str(session.id)
    
    # ── Auto-naming logic ─────────────────────────────────────────────────────
    # If this is a new session OR the current name looks like a default "Chat - Oct 25...", 
    # we generate a new title from the user message.
    if not request.session_id or session.session_name.startswith("Chat - "):
        words = request.message.split()
        # Clean and pick first 7 words
        clean_words = [w.strip('?!.,').capitalize() for w in words if len(w) > 1][:7]
        if clean_words:
            new_title = " ".join(clean_words)
            await update_session_name(db, session_id_str, new_title)

    # ── Store user message ─────────────────────────────────────────────────────
    user_msg = await create_message(
        db=db,
        session_id=session_id_str,
        role="user",
        message_text=request.message,
    )

    # ── Build conversation history ─────────────────────────────────────────────
    previous_messages = await get_session_messages(db, session_id_str, limit=50)
    history = [
        {"role": m.role, "content": m.message_text}
        for m in previous_messages
    ]

    # ── Run agent ──────────────────────────────────────────────────────────────
    try:
        orchestrator = req.app.state.orchestrator
        db_tool = req.app.state.db_tool
        session_mgr = req.app.state.session_manager

        runtime_session_id = await session_mgr.create_session(user_id)

        # ── Multi-DB path ──────────────────────────────────────────────────────
        if len(validated_conns) > 1:
            from backend.data.pool.engine import vector_async_session_maker
            from backend.rag.index.pgvector_manager import PgVectorManager
            from backend.rag.embeddings.service import EmbeddingService
            import json
            
            semantic_contexts = {}
            embedding_svc = EmbeddingService()
            query_vec = await embedding_svc.aembed_query(request.message)
            
            async with vector_async_session_maker() as rag_session:
                rag_svc = PgVectorManager(db_session=rag_session)
                for conn in validated_conns:
                    try:
                        metrics = await rag_svc.search_embeddings(
                            tenant_id=tenant_id, source_id=str(conn.id),
                            type='metric', query_embedding=query_vec, limit=5
                        )
                        semantic_contexts[conn.connection_name] = json.dumps(metrics, default=str)
                    except Exception as e:
                        logger.warning(f"Failed to fetch RAG context for {conn.connection_name}: {e}")
                        semantic_contexts[conn.connection_name] = ""

            from backend.agent.multi_db_orchestrator import MultiDBQueryOrchestrator
            multi_orch = MultiDBQueryOrchestrator()
            
            try:
                multi_result = await multi_orch.run(
                    query=request.message,
                    connections=validated_conns,
                    history=history,
                    semantic_context=semantic_contexts,
                    tenant_id=tenant_id,
                )
            finally:
                await session_mgr.delete_session(runtime_session_id)

            result = {
                "response":     multi_result.get("meta", {}).get("summary") or "Multi-database query completed.",
                "sql":          None,
                "results":      multi_result,  # This is the strict contract dict
                "tool_used":    "multi_db_query",
                "plan":         {},
                "tool_result":  result_to_tool_result(multi_result),
            }

        else:
            # ── Single-DB path (existing behaviour, unchanged) ─────────────────
            db_connected = False
            try:
                await db_tool.connect(
                    session_id=runtime_session_id,
                    host=primary_conn.host,
                    port=primary_conn.port,
                    database=primary_conn.database_name,
                    username=primary_conn.username,
                    password=plaintext_password,
                    connection_id=connection_id,
                )
                db_connected = True
            except Exception as e:
                await session_mgr.delete_session(runtime_session_id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to connect to the database: {str(e)}",
                )

            try:
                result = await orchestrator.run(
                    query=request.message,
                    session_id=runtime_session_id,
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    history=history,
                )
            finally:
                if db_connected:
                    await db_tool.disconnect(runtime_session_id)
                await session_mgr.delete_session(runtime_session_id)

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent processing failed: {str(e)}",
        )

    # ── Store agent response ───────────────────────────────────────────────────
    # The snapshot must be a strict SQLDataContract dict
    snapshot = None
    if result.get("results"):
        snapshot = result["results"]
    elif result.get("tool_result"):
        tool_res = result["tool_result"]
        if isinstance(tool_res, dict):
            snapshot = tool_res.get("data")
        elif hasattr(tool_res, "data"):
            snapshot = tool_res.data

    agent_msg = await create_message(
        db=db,
        session_id=session_id_str,
        role="agent",
        message_text=result.get("response", ""),
        generated_sql=result.get("sql"),
        query_result_snapshot=snapshot,
    )

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
        metadata={"plan": result.get("plan", {}), "session_id": session_id_str},
    )


# ── Legacy stateless endpoint (unchanged) ─────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Send a natural-language message to the AI agent (stateless / Redis session).
    For persistent chat history use POST /api/chat-message instead.
    """
    session_id = request.session_id
    session_mgr = req.app.state.session_manager
    session = await session_mgr.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Please login first.")

    try:
        orchestrator = req.app.state.orchestrator
        result = await orchestrator.run(
            query=request.message,
            session_id=session_id,
        )
        return ChatResponse(
            response=result["response"],
            summary=result.get("summary"),
            sql=result.get("sql"),
            results=result.get("tool_result").data if result.get("tool_result") and hasattr(result.get("tool_result"), "data") else None,
            chart=result.get("chart"),
            tool_used=result.get("tool_used"),
            metadata={**result.get("metadata", {}), "plan": result.get("plan", {})},
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@router.get("/chat/history")
async def get_chat_history(session_id: str, req: Request, limit: int = 50):
    """Retrieve conversation history for a Redis/in-memory session."""
    session_mgr = req.app.state.session_manager
    history = await session_mgr.get_history(session_id, limit=limit)
    return {"session_id": session_id, "messages": history, "count": len(history)}
