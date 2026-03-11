"""
External Database Connection Pool Manager
Ensures that we do NOT open a new DB connection for every request to an external user database.
Maintains a pool of connections keyed by db_connection ID.
"""
from typing import Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
import logging

logger = logging.getLogger(__name__)

class ConnectionPoolManager:
    _pools: Dict[str, AsyncEngine] = {}

    @classmethod
    def get_pool(cls, connection_id: str, db_url: str, **kwargs) -> AsyncEngine:
        """
        Get an existing connection pool for the given connection_id or create a new one.
        """
        if connection_id not in cls._pools:
            logger.info(f"Creating new connection pool for connection {connection_id}")
            pool_size = kwargs.get("pool_size", 5)
            max_overflow = kwargs.get("max_overflow", 10)
            
            # Using pool_pre_ping to check connection validity before leasing
            engine = create_async_engine(
                db_url,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True
            )
            cls._pools[connection_id] = engine
        
        return cls._pools[connection_id]

    @classmethod
    async def close_pool(cls, connection_id: str):
        """
        Dispose the connection pool for a connection_id.
        """
        if connection_id in cls._pools:
            logger.info(f"Disposing connection pool for connection {connection_id}")
            engine = cls._pools.pop(connection_id)
            await engine.dispose()
            
    @classmethod
    async def close_all(cls):
        """
        Dispose all connection pools (useful for graceful shutdown).
        """
        for conn_id, engine in list(cls._pools.items()):
            await engine.dispose()
        cls._pools.clear()

pool_manager = ConnectionPoolManager()
