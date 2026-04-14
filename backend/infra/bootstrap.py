import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import sys

try:
    # Connect to default postgres database to create the new one
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="root",
        host="localhost",
        port="5432"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'ai_agent_db'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE ai_agent_db")
        print("Database 'ai_agent_db' created successfully.")
    else:
        print("Database 'ai_agent_db' already exists.")
        
    # 2. Connect to the new database to try and create the vector extension
    conn_db = psycopg2.connect(
        dbname="ai_agent_db",
        user="postgres",
        password="root",
        host="localhost",
        port="5432"
    )
    conn_db.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor_db = conn_db.cursor()
    try:
        cursor_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("Extension 'vector' enabled successfully (if available).")
    except Exception as e:
        print(f"WARNING: Could not enable 'vector' extension: {e}")
        print("RAG features will require manual installation of pgvector.")
    
    cursor_db.close()
    conn_db.close()

except Exception as e:
    print(f"Error during database bootstrap: {e}")
    sys.exit(1)
