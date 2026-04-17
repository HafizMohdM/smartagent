"""
Diagnostic Script: Find connections for orphans.
"""
import sys
import os
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from backend.data.pool.engine import async_session_maker
from backend.models.query import Query, QueryExecution
from backend.models.db_connection import DBConnection

async def diag():
    orphan_ids = ['60476090-adde-450d-a8b4-7b37751e91a2', 'd1bfdee0-0550-4eab-b836-b3f4cc0eb188']
    async with async_session_maker() as db:
        for qid in orphan_ids:
            res = await db.execute(
                select(Query).options(selectinload(Query.executions)).where(Query.id == qid)
            )
            q = res.scalar_one_or_none()
            if not q: continue
            
            print(f"--- Query {qid} ('{q.title}') ---")
            db_names = set(e.database_name for e in q.executions)
            print(f"Historical DB Names: {db_names}")
            
            for name in db_names:
                c_res = await db.execute(select(DBConnection).where(DBConnection.database_name == name))
                conns = c_res.scalars().all()
                print(f"Found connections for '{name}': {[c.id for c in conns]}")

if __name__ == "__main__":
    asyncio.run(diag())
