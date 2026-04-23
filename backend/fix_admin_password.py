
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
from backend.security.hashing import hash_password

async def fix_users():
    try:
        async with async_session_maker() as db:
            targets = [
                ("admin@admin.local", "admin123", "admin"),
                ("user@user.local", "user123", "user"),
                ("admin@example.com", "admin123", "admin")
            ]
            
            for email, password, role in targets:
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalars().first()
                if user:
                    new_hash = hash_password(password)
                    user.password_hash = new_hash
                    user.status = "approved"
                    user.is_active = True
                    user.role = role
                    print(f"Fixed user: {email}")
                else:
                    print(f"User not found: {email}")
            
            await db.commit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_users())
