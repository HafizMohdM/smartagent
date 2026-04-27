
import asyncio
import os
import sys
from sqlalchemy import select, delete

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.data.pool.session import get_db
from backend.data.pool.engine import async_session_maker
from backend.models.query import Query

async def cleanup_null_queries():
    print("Starting cleanup of queries with NULL generated_sql...")
    async with async_session_maker() as session:
        # Count first
        count_stmt = select(Query).where(Query.generated_sql == None)
        result = await session.execute(count_stmt)
        to_delete = result.scalars().all()
        
        if not to_delete:
            print("No NULL SQL queries found. Database is clean.")
            return

        print(f"Found {len(to_delete)} corrupt queries. Deleting...")
        
        # Delete
        delete_stmt = delete(Query).where(Query.generated_sql == None)
        await session.execute(delete_stmt)
        await session.commit()
        print(f"Successfully deleted {len(to_delete)} corrupt queries.")

if __name__ == "__main__":
    asyncio.run(cleanup_null_queries())
