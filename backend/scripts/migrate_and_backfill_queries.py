"""
Idempotent Backfill Script: SQL Migration to Query Model.

Logic:
1. Identify all queries with null 'generated_sql'.
2. For each query, find the LATEST successful execution record.
3. Update the query with that SQL.
4. Log results (migrated, skipped, errors).
"""

import sys
import os
import asyncio
import logging
from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload

# Add project root (parent of backend) to sys.path
# script is in backend/scripts/migrate...
# parent of backend is 3 levels up from this script? No, backend is 1 up, root is 2 up.
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)


from backend.data.pool.engine import async_session_maker
from backend.models.query import Query, QueryExecution

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def run_backfill():
    logger.info("Starting SQL Backfill migration...")
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    skipped_ids = []

    async with async_session_maker() as db:
        # 1. Fetch queries needing backfill
        result = await db.execute(
            select(Query)
            .options(selectinload(Query.executions))
            .where(Query.generated_sql.is_(None))
        )
        queries = result.scalars().all()
        
        logger.info(f"Checking {len(queries)} queries for SQL backfill.")

        for q in queries:
            # Guarantee 2: Deterministic Backfill (Latest successful)
            # Executions are sorted by created_at desc if we want latest
            successful_execs = sorted(
                [e for e in q.executions if e.status == "success" and e.sql],
                key=lambda x: x.created_at,
                reverse=True
            )

            if successful_execs:
                target_sql = successful_execs[0].sql
                q.generated_sql = target_sql
                migrated_count += 1
                logger.info(f"[Migrated] Query {q.id} -> SQL extracted from execution {successful_execs[0].id}")
            else:
                skipped_count += 1
                skipped_ids.append(str(q.id))
                logger.warning(f"[Skipped] Query {q.id} -> No successful execution found.")

        # Commit backfill changes
        await db.commit()

    logger.info("=" * 40)
    logger.info(f"Backfill Complete")
    logger.info(f"Migrated: {migrated_count}")
    logger.info(f"Skipped:  {skipped_count}")
    if skipped_ids:
        logger.info(f"Skipped IDs: {', '.join(skipped_ids)}")
    logger.info("=" * 40)
    
    if migrated_count > 0:
        logger.info("SUCCESS: SQL definitions migrated to Source of Truth.")
    else:
        logger.info("NOTE: No queries required migration.")

if __name__ == "__main__":
    asyncio.run(run_backfill())
