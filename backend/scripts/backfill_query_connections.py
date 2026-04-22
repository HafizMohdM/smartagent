import asyncio
import argparse
import sys
import os
import uuid
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from backend.data.pool.engine import async_session_maker
from backend.models.query import Query, QueryExecution
from backend.models.db_connection import DBConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill-queries")

async def backfill_query_connections(dry_run: bool = True):
    """
    Idempotent script to backfill query_connections based on execution history.
    """
    logger.info("=" * 60)
    logger.info(f"  QUERY-CONNECTION BACKFILL (Dry Run: {dry_run})")
    logger.info("=" * 60)

    async with async_session_maker() as db:
        # Fetch all queries that have no connections linked
        # We use selectinload(Query.connections) to check current state
        result = await db.execute(select(Query).options(selectinload(Query.connections), selectinload(Query.executions)))
        queries = result.scalars().all()

        migration_stats = {"mapped": 0, "skipped": 0, "errors": 0}

        for q in queries:
            if q.connections:
                logger.info(f"[Skip] Query '{q.title}' ({q.id}) already has connections mapped.")
                migration_stats["skipped"] += 1
                continue

            # Identify target connections from executions
            target_db_names = set()
            for ex in q.executions:
                if ex.database_name:
                    target_db_names.add(ex.database_name)

            if not target_db_names:
                logger.warning(f"[Warn] Query '{q.title}' ({q.id}) has no execution history. Cannot backfill.")
                migration_stats["skipped"] += 1
                continue

            # Find matching connections in the same tenant
            conn_result = await db.execute(
                select(DBConnection).where(
                    DBConnection.database_name.in_(list(target_db_names)),
                    DBConnection.tenant_id == q.tenant_id
                )
            )
            found_conns = list(conn_result.scalars().all())

            if not found_conns:
                logger.warning(f"[Warn] No DBConnection objects found for databases {target_db_names} in tenant {q.tenant_id}.")
                migration_stats["errors"] += 1
                continue

            logger.info(f"[Link] Mapping query '{q.title}' to databases: {[c.database_name for c in found_conns]}")
            
            if not dry_run:
                q.connections = found_conns
                migration_stats["mapped"] += 1
            else:
                migration_stats["mapped"] += 1

        if not dry_run:
            await db.commit()
            logger.info("✓ Backfill committed successfully.")
        else:
            logger.info("✓ Dry run complete. No changes made to DB.")

        logger.info("-" * 60)
        logger.info(f"Final Stats: {migration_stats}")
        logger.info("-" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill query_connections table.")
    parser.add_argument("--execute", action="store_true", help="Run migration (defaults to dry-run)")
    args = parser.parse_args()

    asyncio.run(backfill_query_connections(dry_run=not args.execute))
