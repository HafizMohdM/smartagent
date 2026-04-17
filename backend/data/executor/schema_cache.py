"""
Schema Cache — Async, per-database TTL cache for table names.
Avoids hitting information_schema on every query execution.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.data.connector.connector import DatabaseConnector
from backend.data.pool.manager import pool_manager
from backend.models.db_connection import DBConnection
from backend.security.encryption import decrypt_password

logger = logging.getLogger(__name__)

# Default cache lifetime: 5 minutes
DEFAULT_TTL_SECONDS = 300


class _CacheEntry:
    __slots__ = ("tables", "expires_at")

    def __init__(self, tables: Set[str], ttl: float):
        self.tables = tables
        self.expires_at = time.monotonic() + ttl


class SchemaCache:
    """
    Global singleton that maps connection_id → set of table names.
    Thread-safe via per-key asyncio locks.
    """

    def __init__(self, ttl: float = DEFAULT_TTL_SECONDS):
        self._ttl = ttl
        self._store: Dict[str, _CacheEntry] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a per-key lock (non-async helper)."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get_tables(self, conn: DBConnection) -> Set[str]:
        """
        Return the set of table names for a connection.
        Uses cache if fresh; otherwise introspects the DB.
        """
        key = str(conn.id)

        # Fast path: check cache without lock
        entry = self._store.get(key)
        if entry and time.monotonic() < entry.expires_at:
            return entry.tables

        # Slow path: acquire per-key lock, introspect
        async with self._global_lock:
            lock = self._get_lock(key)

        async with lock:
            # Double-check after acquiring lock
            entry = self._store.get(key)
            if entry and time.monotonic() < entry.expires_at:
                return entry.tables

            tables = await self._introspect(conn)
            self._store[key] = _CacheEntry(tables, self._ttl)
            logger.info(f"SchemaCache: cached {len(tables)} tables for '{conn.connection_name or conn.database_name}'")
            return tables

    async def _introspect(self, conn: DBConnection) -> Set[str]:
        """Query information_schema for table names (lightweight, async)."""
        try:
            plaintext = decrypt_password(conn.encrypted_password)
            async_url = (
                f"postgresql+asyncpg://{conn.username}:{plaintext}"
                f"@{conn.host}:{conn.port}/{conn.database_name}"
            )
            pool_key = f"{conn.host}:{conn.port}/{conn.database_name}:{conn.username}"
            engine: AsyncEngine = pool_manager.get_pool(connection_id=pool_key, db_url=async_url)

            async with engine.connect() as connection:
                result = await connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                    )
                )
                rows = result.fetchall()
                return {row[0].lower() for row in rows}

        except Exception as e:
            logger.error(f"SchemaCache introspection failed for {conn.database_name}: {e}")
            # Return empty set — execution will be attempted and may fail naturally
            return set()

    def invalidate(self, connection_id: str) -> None:
        """Remove a specific connection from the cache."""
        self._store.pop(connection_id, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        self._store.clear()


# ── Module-level singleton ─────────────────────────────────────────
schema_cache = SchemaCache()
