"""
Session memory manager backed by Redis.
Manages conversation history, active service connections,
and agent state per user session. Falls back to in-memory
storage if Redis is unavailable.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions, conversation history, and connection state."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_store: Dict[str, Dict[str, Any]] = {}  # fallback

    @property
    def _use_redis(self) -> bool:
        return self._redis is not None

    # ── Session lifecycle ──────────────────────────────────────────────

    async def create_session(self, user_id: str) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
            "connections": {},
            "metadata": {},
        }
        await self._store_session(session_id, session_data)
        logger.info(f"Session created: {session_id} for user {user_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full session data."""
        return await self._load_session(session_id)

    async def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        if self._use_redis:
            await self._redis.delete(f"session:{session_id}")
        else:
            self._local_store.pop(session_id, None)
        logger.info(f"Session deleted: {session_id}")

    # ── Message history ────────────────────────────────────────────────

    async def add_message(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Append a message to the session conversation history."""
        session = await self._load_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session["messages"].append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        await self._store_session(session_id, session)

    async def get_history(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, str]]:
        """Return the last `limit` messages for a session."""
        session = await self._load_session(session_id)
        if session is None:
            return []
        return session["messages"][-limit:]

    # ── Connection tracking ────────────────────────────────────────────

    async def store_connection(
        self, session_id: str, service_name: str, connection_info: Dict[str, Any]
    ) -> None:
        """Record an active service connection in the session."""
        session = await self._load_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session["connections"][service_name] = {
            **connection_info,
            "connected_at": datetime.utcnow().isoformat(),
        }
        await self._store_session(session_id, session)

    async def get_connection(
        self, session_id: str, service_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve connection info for a service in a session."""
        session = await self._load_session(session_id)
        if session is None:
            return None
        return session.get("connections", {}).get(service_name)

    # ── Metadata ───────────────────────────────────────────────────────

    async def update_metadata(
        self, session_id: str, key: str, value: Any
    ) -> None:
        """Store arbitrary metadata in the session."""
        session = await self._load_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session["metadata"][key] = value
        await self._store_session(session_id, session)

    # ── Internal persistence ───────────────────────────────────────────

    async def _store_session(
        self, session_id: str, data: Dict[str, Any]
    ) -> None:
        if self._use_redis:
            await self._redis.set(
                f"session:{session_id}",
                json.dumps(data),
                ex=86400,  # 24-hour TTL
            )
        else:
            self._local_store[session_id] = data

    async def _load_session(
        self, session_id: str
    ) -> Optional[Dict[str, Any]]:
        if self._use_redis:
            raw = await self._redis.get(f"session:{session_id}")
            return json.loads(raw) if raw else None
        return self._local_store.get(session_id)
