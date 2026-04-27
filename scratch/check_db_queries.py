import asyncio
import os
import sys
sys.path.append(os.getcwd())

from backend.data.pool.engine import async_session_maker
from backend.models.query import Query
from sqlalchemy import select

async def run():
    async with async_session_maker() as db:
        res = await db.execute(select(Query).order_by(Query.created_at.desc()).limit(2))
        for q in res.scalars():
            print(f"ID: {q.id}")
            print(f"Title: {q.title}")
            print(f"Text: {q.query_text[:100]}")
            print(f"SQL: {q.generated_sql[:200] if q.generated_sql else 'NONE'}")
            print(f"---")

if __name__ == "__main__":
    asyncio.run(run())
