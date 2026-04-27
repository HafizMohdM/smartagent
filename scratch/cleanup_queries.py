import asyncio
import os
import sys
sys.path.append(os.getcwd())

from backend.data.pool.engine import async_session_maker
from backend.models.query import Query
from sqlalchemy import update, or_

async def run():
    async with async_session_maker() as db:
        # Nullify any generated_sql that doesn't look like SQL or contains error tags
        stmt = (
            update(Query)
            .where(
                or_(
                    Query.generated_sql.like("%TYPE: ERROR%"),
                    Query.generated_sql.like("%| --- |%"),
                    Query.generated_sql == ""
                )
            )
            .values(generated_sql=None)
        )
        result = await db.execute(stmt)
        await db.commit()
        print(f"Cleaned up {result.rowcount} invalid queries.")

if __name__ == "__main__":
    asyncio.run(run())
