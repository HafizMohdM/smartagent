"""
Backfill Script — Migrates legacy JSON-based semantic data into tenant_embeddings.
"""

import asyncio
import json
import os
import logging
from uuid import UUID
from backend.rag.embeddings.service import EmbeddingService
from backend.rag.index.pgvector_manager import PgVectorManager
from backend.data.pool.engine import vector_async_session_maker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LEGACY_PATH = "./vector_store/semantic"

async def backfill(tenant_id: str, connection_id: str):
    """Migrates metrics, entities, and relationships for a specific connection."""
    logger.info(f"Starting backfill for tenant {tenant_id}, connection {connection_id}")
    
    embedding_svc = EmbeddingService()
    
    async with vector_async_session_maker() as session:
        rag_svc = PgVectorManager(db_session=session)
        
        # 1. Migrate Metrics
        metrics_file = os.path.join(LEGACY_PATH, "metrics.json")
        if os.path.exists(metrics_file):
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
                for name, data in metrics.items():
                    logger.info(f"Migrating metric: {name}")
                    content = f"{data['name']}: {data['description']}"
                    embedding = await embedding_svc.aembed_query(content)
                    await rag_svc.upsert_embedding(
                        tenant_id=tenant_id,
                        source_id=connection_id,
                        type="metric",
                        key=name,
                        content=content,
                        meta_data=data,
                        embedding=embedding
                    )

        # 2. Migrate Entities
        entities_file = os.path.join(LEGACY_PATH, "entities.json")
        if os.path.exists(entities_file):
            with open(entities_file, 'r') as f:
                entities = json.load(f)
                for name, data in entities.items():
                    logger.info(f"Migrating entity: {name}")
                    await rag_svc.upsert_embedding(
                        tenant_id=tenant_id,
                        source_id=connection_id,
                        type="entity",
                        key=name,
                        content=f"{data['name']}: {data['description']}",
                        meta_data=data,
                        embedding=None
                    )

        # 3. Migrate Relationships
        rel_file = os.path.join(LEGACY_PATH, "relationships.json")
        if os.path.exists(rel_file):
            with open(rel_file, 'r') as f:
                relationships = json.load(f)
                for rel in relationships:
                    key = f"{rel['source_entity']}_{rel['target_entity']}"
                    logger.info(f"Migrating relationship: {key}")
                    await rag_svc.upsert_embedding(
                        tenant_id=tenant_id,
                        source_id=connection_id,
                        type="relationship",
                        key=key,
                        content=key,
                        meta_data=rel,
                        embedding=None
                    )

    logger.info("✓ Backfill completed successfully.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python backfill_embeddings.py <tenant_id> <connection_id>")
        sys.exit(1)
    
    t_id = sys.argv[1]
    c_id = sys.argv[2]
    asyncio.run(backfill(t_id, c_id))
