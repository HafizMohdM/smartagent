"""
Database Connector — manages async SQLAlchemy connections to PostgreSQL.
Handles connect/disconnect lifecycle, schema introspection, and raw query execution.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import text, inspect
from sqlalchemy.engine import create_engine
from backend.database.connection_pool_manager import pool_manager

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """Async PostgreSQL connector using SQLAlchemy."""

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sync_engine = None
        self._connection_info: Dict[str, Any] = {}

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    async def connect(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
    ) -> Dict[str, str]:
        """
        Establish an async connection to the PostgreSQL database.
        Returns connection status info.
        """
        try:
            async_url = (
                f"postgresql+asyncpg://{username}:{password}"
                f"@{host}:{port}/{database}"
            )
            sync_url = (
                f"postgresql://{username}:{password}"
                f"@{host}:{port}/{database}"
            )

            # Use ConnectionPoolManager for async engine to avoid connection-per-request
            connection_id = f"{host}:{port}/{database}:{username}"
            self._engine = pool_manager.get_pool(connection_id=connection_id, db_url=async_url)
            
            # Keep sync engine strictly for schema introspection
            self._sync_engine = create_engine(sync_url, echo=False)

            # Test the connection
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()

            self._connection_info = {
                "host": host,
                "port": port,
                "database": database,
                "username": username,
            }
            logger.info(f"Connected to database: {database}@{host}:{port}")
            return {"status": "connected", "database": database, "host": host}

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self._engine = None
            self._sync_engine = None
            raise ConnectionError(f"Failed to connect to database: {str(e)}")

    async def disconnect(self) -> None:
        """Close the database connection manually via pool manager if necessary."""
        if self._engine:
            # We don't dispose the engine since it's managed by the pool manager,
            # unless we explicitly want to kill all connections for this DB.
            # But we can release the reference.
            self._engine = None
        if self._sync_engine:
            self._sync_engine.dispose()
            self._sync_engine = None
        self._connection_info = {}
        logger.info("Database connection reference released.")

    def get_schema(self) -> Dict[str, Any]:
        """
        Introspect the database and return its full schema.
        Returns a dict mapping table names to their column definitions.
        """
        if self._sync_engine is None:
            raise ConnectionError("Not connected to any database.")

        inspector = inspect(self._sync_engine)
        schema: Dict[str, Any] = {}

        for table_name in inspector.get_table_names():
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": str(col.get("default")) if col.get("default") else None,
                })

            # Primary keys
            pk = inspector.get_pk_constraint(table_name)
            pk_columns = pk.get("constrained_columns", []) if pk else []

            # Foreign keys
            fks = inspector.get_foreign_keys(table_name)
            foreign_keys = [
                {
                    "columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"],
                }
                for fk in fks
            ]

            schema[table_name] = {
                "columns": columns,
                "primary_keys": pk_columns,
                "foreign_keys": foreign_keys,
            }

        logger.info(f"Schema loaded: {len(schema)} tables")
        return schema

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a read-only SQL query and return results as a list of dicts."""
        if self._engine is None:
            raise ConnectionError("Not connected to any database.")

        async with self._engine.connect() as conn:
            result = await conn.execute(text(sql))
            columns = list(result.keys())
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
