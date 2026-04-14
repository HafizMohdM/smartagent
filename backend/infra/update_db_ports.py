
import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from backend directory
load_dotenv(os.path.join(os.getcwd(), "backend", ".env"))

DATABASE_URL = os.getenv("APP_DATABASE_URL")

async def update_ports():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print(f"Connecting to {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Searching for connections on port 5432...")
        # Check how many will be updated
        select_result = await conn.execute(text("SELECT id, connection_name FROM db_connections WHERE port = 5432"))
        to_update = select_result.fetchall()
        
        if not to_update:
            print("No connections found on port 5432.")
        else:
            print(f"Found {len(to_update)} connection(s) to update.")
            for row in to_update:
                print(f"  - Updating connection: {row.connection_name} ({row.id})")
            
            # Update
            update_result = await conn.execute(
                text("UPDATE db_connections SET port = 5433 WHERE port = 5432")
            )
            print(f"Successfully updated {update_result.rowcount} row(s).")

    print("Checking final state...")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT connection_name, port FROM db_connections"))
        for row in result:
            print(f"Connection: {row.connection_name} | Port: {row.port}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(update_ports())
