"""
 Integrity Check: Post-Migration Validator.

 Verifies:
 1. Every query has a non-null 'generated_sql'.
 2. Every query has at least one associated connection in 'query_connections'.
"""

import sys
import os
import asyncio
import logging
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from backend.data.pool.engine import async_session_maker
from backend.models.query import Query

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def run_integrity_check():
    logger.info("Starting Post-Migration Integrity Check...")
    
    orphan_sql_count = 0
    orphan_conn_count = 0
    total_queries = 0

    async with async_session_maker() as db:
        result = await db.execute(
            select(Query).options(selectinload(Query.connections))
        )
        queries = result.scalars().all()
        total_queries = len(queries)

        for q in queries:
            # Check SQL
            if not q.generated_sql:
                logger.error(f"[ORPHAN] Query {q.id} ('{q.title}') is missing generated_sql!")
                orphan_sql_count += 1
            
            # Check Connections
            if not q.connections:
                logger.error(f"[ORPHAN] Query {q.id} ('{q.title}') has no associated database connections!")
                orphan_conn_count += 1

    logger.info("=" * 40)
    logger.info(f"Integrity Report")
    logger.info(f"Total Queries: {total_queries}")
    logger.info(f"Orphan SQL:    {orphan_sql_count}")
    logger.info(f"Orphan Conns:  {orphan_conn_count}")
    logger.info("=" * 40)
    
    if orphan_sql_count == 0 and orphan_conn_count == 0:
        logger.info("✓ PASS: All queries are valid and traceable.")
    else:
        logger.error("✗ FAIL: Integrity violations found. Manual intervention required.")

if __name__ == "__main__":
    asyncio.run(run_integrity_check())
