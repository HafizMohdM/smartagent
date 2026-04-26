"""
Semantic Cache for storing and retrieving previously successful query results.
Tenant isolated via pgvector.
"""

import logging
from typing import Optional, Dict, Any
from backend.rag.index.pgvector_manager import PgVectorManager
from backend.rag.embeddings.service import EmbeddingService
from backend.data.pool.engine import vector_async_session_maker

logger = logging.getLogger(__name__)

class SemanticCache:
    """Provides vector-similarity based caching for natural language queries, isolated by tenant."""
    
    def __init__(self, embedding_service: EmbeddingService, threshold: float = 0.1):
        self.embedding_service = embedding_service
        self.threshold = threshold # Cosine distance threshold (lower is better)

    async def lookup(self, tenant_id: str, source_id: str, query: str) -> Optional[Dict[str, Any]]:
        """Check if a similar query exists in cache for this specific tenant and source."""
        try:
            query_embedding = await self.embedding_service.aembed_query(query)
            
            async with vector_async_session_maker() as session:
                rag_svc = PgVectorManager(db_session=session)
                results = await rag_svc.search_embeddings(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    type='cache',
                    query_embedding=query_embedding,
                    limit=1
                )
                
                if results:
                    hit = results[0]
                    # PgVectorManager returns cosine distance (0 to 2)
                    if hit['distance'] < self.threshold:
                        logger.info(f"⚡ Semantic cache HIT for tenant {tenant_id} (dist={hit['distance']:.4f})")
                        return hit['metadata'].get('result') if hit.get('metadata') else None
                    else:
                        logger.debug(f"Semantic cache MISS for tenant {tenant_id} (closest dist={hit['distance']:.4f})")
            
            return None
        except Exception as e:
            logger.error(f"Error in semantic cache lookup: {e}")
            return None

    async def update(self, tenant_id: str, source_id: str, query: str, result: Dict[str, Any]):
        """Save a new successful result to the semantic cache for this specific tenant and source."""
        try:
            query_embedding = await self.embedding_service.aembed_query(query)
            
            async with vector_async_session_maker() as session:
                rag_svc = PgVectorManager(db_session=session)
                # Use query as key (or a hash of it) to allow upserts if same query comes in
                # However, semantic cache usually doesn't need unique keys per query if we just append,
                # but for cleanup/management, a key might be useful.
                import hashlib
                query_key = hashlib.sha256(query.encode()).hexdigest()
                
                await rag_svc.upsert_embedding(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    type='cache',
                    key=query_key,
                    content=query,
                    meta_data={"query": query, "result": result},
                    embedding=query_embedding
                )
            logger.info(f"✓ Semantic cache updated for tenant {tenant_id}, source {source_id}")
        except Exception as e:
            logger.error(f"Error updating semantic cache: {e}")
