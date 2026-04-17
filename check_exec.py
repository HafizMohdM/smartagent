import asyncio
from backend.data.pool.session import AsyncSessionLocal
from backend.models.query import Query, QueryExecution
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Query).options(selectinload(Query.executions)).order_by(Query.created_at.desc()).limit(1))
        q = result.scalars().first()
        print(f"Executions length: {len(q.executions)}")
        for e in q.executions:
            print(f"result_json type: {type(e.result_json)}")
            if isinstance(e.result_json, dict):
                print(f"keys: {list(e.result_json.keys())}")
                if 'data' in e.result_json: print(f"data is list: {isinstance(e.result_json['data'], list)}")
                if 'rows' in e.result_json: print(f"rows is list: {isinstance(e.result_json['rows'], list)}")

asyncio.run(main())
