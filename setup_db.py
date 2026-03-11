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
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error creating database: {e}")
    sys.exit(1)
