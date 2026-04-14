import asyncio
from backend.data.pool.engine import async_session_maker
from backend.models.db_connection import DBConnection
from backend.models.tenant import Tenant
from sqlalchemy import select

async def get_valid_connection():
    async with async_session_maker() as session:
        # Check for any connection
        result = await session.execute(select(DBConnection.id).limit(1))
        conn_id = result.scalars().first()
        if conn_id:
            print(conn_id)
            return
            
        # If no connection, find a tenant to link to
        result = await session.execute(select(Tenant.id).limit(1))
        tenant_id = result.scalars().first()
        print(f"TENANT:{tenant_id}")

if __name__ == "__main__":
    asyncio.run(get_valid_connection())
