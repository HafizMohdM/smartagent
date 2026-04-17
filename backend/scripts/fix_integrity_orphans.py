"""
 Integrity Fixer: Remove un-runnable orphans.
 
 Logic:
 1. Identify queries with no connections.
 2. Delete them (they are un-runnable artifacts of deleted DBs).
"""
import sys
import os
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from backend.data.pool.engine import async_session_maker
from backend.models.query import Query

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def fix_integrity():
    logger.info("Starting Integrity Restoration...")
    deleted_count = 0

    async with async_session_maker() as db:
        result = await db.execute(
            select(Query).options(selectinload(Query.connections))
        )
        queries = result.scalars().all()

        for q in queries:
            if not q.connections:
                logger.warning(f"[REMOVING ORPHAN] Query {q.id} ('{q.title}') - No active connections found.")
                await db.delete(q)
                deleted_count += 1
        
        await db.commit()

    logger.info(f"Integrity restoration finished. Deleted {deleted_count} stale orphans.")

if __name__ == "__main__":
    asyncio.run(fix_integrity())
