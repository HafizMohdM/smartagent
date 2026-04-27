
import os
import sys
import asyncio

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from sqlalchemy.future import select
from backend.data.pool.engine import async_session_maker
from backend.models.user import User

async def check_users():
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
            print(f"Total users found: {len(users)}")
            for user in users:
                print(f"User: {user.email}, Role: {user.role}, Status: {user.status}")
    except Exception as e:
        print(f"Error checking users: {e}")

if __name__ == "__main__":
    asyncio.run(check_users())
