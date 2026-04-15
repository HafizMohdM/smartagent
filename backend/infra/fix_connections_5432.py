
import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from backend directory
# Use the NEWly updated .env which points to 5432
load_dotenv(os.path.join(os.getcwd(), "backend", ".env"))

DATABASE_URL = os.getenv("APP_DATABASE_URL")

async def fix_connections():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print(f"Connecting to {DATABASE_URL} to fix metadata...")
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        # 1. Update all connections to port 5432
        print("Updating all connections to port 5432...")
        update_ports = await conn.execute(
            text("UPDATE db_connections SET port = 5432")
        )
        print(f"Updated {update_ports.rowcount} row(s) to port 5432.")

        # 2. Fix horilla typo
        print("Checking for horilla_new_main typo...")
        fix_typo = await conn.execute(
            text("UPDATE db_connections SET database_name = 'horilla_main_new' WHERE database_name = 'horilla_new_main'")
        )
        print(f"Fixed {fix_typo.rowcount} typo(s) for 'horilla_main_new'.")

    print("\nChecking final state of connections:")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, connection_name, port, database_name FROM db_connections"))
        for row in result:
            print(f"ID: {row.id} | Name: {row.connection_name} | Port: {row.port} | DB: {row.database_name}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_connections())
