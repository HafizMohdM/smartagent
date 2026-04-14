import asyncio
import uuid
import logging
from uuid import UUID
from backend.data.connector.connector import DatabaseConnector
from backend.data.retrieval.ingestion import SchemaIngestionService
from backend.rag.embeddings.service import EmbeddingService
from backend.data.executor.generator import SQLGenerator
from backend.models.table_metadata import TableMetadataStore
from backend.data.pool.engine import async_session_maker
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_phase2():
    # 1. Setup
    embedding_service = EmbeddingService()
    ingestion_service = SchemaIngestionService(embedding_service)
    generator = SQLGenerator()
    
    # Use a valid connection_id from the database to satisfy Foreign Key constraints
    test_uuid_str = "87d83a87-7ab5-4063-89b5-d2fbc6db964c"
    connector = DatabaseConnector()
    
    await connector.connect(
        host="localhost",
        port=5432,
        database="ai_agent_db",
        username="postgres",
        password="root",
        connection_id=test_uuid_str
    )
    
    connection_id = UUID(test_uuid_str)
    print(f"Verified Connection ID: {connection_id}")
    
    try:
        # 2. Trigger Ingestion
        logger.info("--- Step 1: Triggering Ingestion ---")
        await ingestion_service.sync_schema(connection_id, connector)
        
        # 3. Verify Database Store
        logger.info("--- Step 2: Verifying Metadata Store ---")
        async with async_session_maker() as session:
            stmt = select(TableMetadataStore).where(TableMetadataStore.connection_id == connection_id)
            result = await session.execute(stmt)
            tables = result.scalars().all()
            logger.info(f"Found {len(tables)} tables in metadata store.")
            for t in tables[:3]: # Log first 3
                logger.info(f"Table: {t.table_name}, Columns: {len(t.columns)}, FKs: {len(t.relationships or [])}")
        
        # 4. Verify Hybrid Retrieval
        logger.info("--- Step 3: Verifying Retrieval ---")
        schema = connector.get_schema()
        # Test with a query that should match one of our tables (e.g. users or chat_sessions)
        query = "show all users"
        sql = await generator.generate(query, schema, connection_id=str(connection_id))
        logger.info(f"GENERATED SQL:\n{sql}")
        
    finally:
        await connector.disconnect()

if __name__ == "__main__":
    asyncio.run(verify_phase2())
