import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, List
from backend.config.settings import settings

logger = logging.getLogger(__name__)

class ReportDataCache:
    """
    Production-grade cache for report data with Redis support and stampede protection.
    """
    _in_memory_cache: Dict[str, Dict[str, Any]] = {}
    _locks: Dict[str, asyncio.Lock] = {}
    _global_lock = asyncio.Lock()

    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client

    def generate_key(self, query_id: str, sql: str, connection_ids: List[str]) -> str:
        """
        Derive a unique cache key from query_id, SQL hash, and connections.
        """
        sorted_conns = sorted([str(cid) for cid in connection_ids])
        sql_hash = hashlib.sha256(sql.strip().encode()).hexdigest()
        raw_key = f"report:{query_id}:{sql_hash}:{','.join(sorted_conns)}"
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for a specific cache key (stampede protection)."""
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Redis or in-memory cache."""
        # 1. Try Redis
        if self.redis:
            try:
                data = await self.redis.get(key)
                if data:
                    logger.debug(f"[Cache] HIT (Redis) for {key}")
                    return json.loads(data)
            except Exception as e:
                logger.error(f"[Cache] Redis error: {e}")

        # 2. Fallback to in-memory
        cached = self._in_memory_cache.get(key)
        if cached:
            if cached["expiry"] > time.time():
                logger.debug(f"[Cache] HIT (Memory) for {key}")
                return cached["data"]
            else:
                del self._in_memory_cache[key]
        
        logger.debug(f"[Cache] MISS for {key}")
        return None

    async def set(self, key: str, data: Dict[str, Any], ttl: int = 30):
        """Store data in cache."""
        # 1. Set in Redis
        if self.redis:
            try:
                await self.redis.set(key, json.dumps(data), ex=ttl)
                logger.debug(f"[Cache] SET (Redis) for {key} TTL={ttl}")
            except Exception as e:
                logger.error(f"[Cache] Redis set error: {e}")

        # 2. Set in-memory
        self._in_memory_cache[key] = {
            "data": data,
            "expiry": time.time() + ttl
        }
        logger.debug(f"[Cache] SET (Memory) for {key} TTL={ttl}")

    async def invalidate(self, query_id: str):
        """
        Invalidate all cache entries related to a query.
        In a production Redis setup, this might use 'KEYS report:{query_id}*' and DEL.
        For simplified in-memory, we just clear the whole thing or filter.
        """
        # Note: In production, we'd use a more surgical invalidation.
        # For now, we'll clear entries that we can identify.
        # This is a placeholder for more advanced pattern-based invalidation.
        logger.info(f"[Cache] Invalidation triggered for query {query_id}")
        if self.redis:
            # surgical redis invalidation would go here
            pass
        
        # Simple in-memory purge
        self._in_memory_cache = {}
