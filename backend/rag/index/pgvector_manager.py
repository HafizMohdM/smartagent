import logging
import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from sqlalchemy.dialects.postgresql import insert

from backend.models.knowledge_base_chunk import KnowledgeBaseChunk
from backend.models.table_metadata import TableMetadataStore
from backend.models.tenant_embedding import TenantEmbedding

logger = logging.getLogger(__name__)

def assert_isolation_context(tenant_id: Any, source_id: Any):
    """MANDATORY: Global validation gate for all vector operations."""
    assert tenant_id is not None, "Missing isolation context: tenant_id is required"
    assert source_id is not None, "Missing isolation context: source_id is required"

class PgVectorManager:
    """
    Universal tenant-isolated pgvector service.
    Handles metrics, cache, entities, relationships, schema, and documents.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def _execute_vector_search(self, stmt, limit: int, threshold: float = None):
        """Helper to execute an HNSW query with a guardrail retry."""
        try:
            # 1. First attempt with iterative scan
            await self.db_session.execute(text("SET LOCAL hnsw.iterative_scan = on"))
            result = await self.db_session.execute(stmt)
            rows = list(result.all())
            
            # Check if we got enough results (guardrail)
            if len(rows) < limit:
                logger.warning(f"HNSW scan returned <k rows ({len(rows)} < {limit}). Retrying with higher ef_search.")
                await self.db_session.execute(text("SET LOCAL hnsw.ef_search = 200"))
                result = await self.db_session.execute(stmt)
                rows = list(result.all())
                
            return rows
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise

    async def search_schema(
        self, tenant_id: str, connection_id: str,
        query_embedding: List[float], limit: int = 5
    ) -> List[Dict[str, Any]]:
        assert_isolation_context(tenant_id, connection_id)
        
        stmt = (
            select(
                TableMetadataStore.table_name,
                TableMetadataStore.description,
                TableMetadataStore.columns,
                TableMetadataStore.embedding.cosine_distance(query_embedding).label("distance")
            )
            .where(
                TableMetadataStore.tenant_id == tenant_id,
                TableMetadataStore.connection_id == connection_id
            )
            .order_by(TableMetadataStore.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        
        rows = await asyncio.wait_for(self._execute_vector_search(stmt, limit), timeout=3.0)
        
        formatted_results = []
        for row in rows:
            formatted_results.append({
                "table_name": row.table_name,
                "description": row.description,
                "columns": row.columns,
                "distance": row.distance
            })
            
        logger.info(f"[RAG] tenant={tenant_id} source={connection_id} type=schema results={len(formatted_results)}")
        return formatted_results

    async def search_embeddings(
        self, tenant_id: str, source_id: str, type: str,
        query_embedding: List[float], limit: int = 5
    ) -> List[Dict[str, Any]]:
        assert_isolation_context(tenant_id, source_id)
        
        stmt = (
            select(
                TenantEmbedding.content,
                TenantEmbedding.meta_data,
                TenantEmbedding.embedding.cosine_distance(query_embedding).label("distance")
            )
            .where(
                TenantEmbedding.tenant_id == tenant_id,
                TenantEmbedding.source_id == source_id,
                TenantEmbedding.type == type,
                TenantEmbedding.embedding.is_not(None)
            )
            .order_by(TenantEmbedding.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        
        rows = await asyncio.wait_for(self._execute_vector_search(stmt, limit), timeout=3.0)
        
        formatted_results = []
        for row in rows:
            formatted_results.append({
                "content": row.content,
                "metadata": row.meta_data,
                "distance": row.distance
            })
            
        logger.info(f"[RAG] tenant={tenant_id} source={source_id} type={type} results={len(formatted_results)}")
        return formatted_results

    async def get_entities(self, tenant_id: str, source_id: str) -> List[Dict[str, Any]]:
        assert_isolation_context(tenant_id, source_id)
        stmt = select(TenantEmbedding).where(
            TenantEmbedding.tenant_id == tenant_id,
            TenantEmbedding.source_id == source_id,
            TenantEmbedding.type == 'entity'
        )
        result = await self.db_session.execute(stmt)
        return [row.meta_data for row in result.scalars().all()]

    async def get_relationships(self, tenant_id: str, source_id: str) -> List[Dict[str, Any]]:
        assert_isolation_context(tenant_id, source_id)
        stmt = select(TenantEmbedding).where(
            TenantEmbedding.tenant_id == tenant_id,
            TenantEmbedding.source_id == source_id,
            TenantEmbedding.type == 'relationship'
        )
        result = await self.db_session.execute(stmt)
        return [row.meta_data for row in result.scalars().all()]

    async def upsert_embedding(
        self, tenant_id: str, source_id: str, type: str,
        content: str, meta_data: Dict[str, Any] = None, embedding: List[float] = None,
        key: str = None
    ):
        assert_isolation_context(tenant_id, source_id)
        
        stmt = insert(TenantEmbedding).values(
            tenant_id=tenant_id,
            source_id=source_id,
            type=type,
            key=key,
            content=content,
            meta_data=meta_data,
            embedding=embedding
        )
        
        if key:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_tenant_source_type_key",
                set_={
                    "content": content,
                    "meta_data": meta_data,
                    "embedding": embedding,
                    "updated_at": text("NOW()")
                }
            )
            
        await self.db_session.execute(stmt)
        await self.db_session.commit()
        logger.info(f"✓ Upserted {type} for tenant {tenant_id}, source {source_id}")

    async def delete_by_source(self, tenant_id: str, source_id: str, type: str = None):
        assert_isolation_context(tenant_id, source_id)
        stmt = delete(TenantEmbedding).where(
            TenantEmbedding.tenant_id == tenant_id,
            TenantEmbedding.source_id == source_id
        )
        if type:
            stmt = stmt.where(TenantEmbedding.type == type)
            
        await self.db_session.execute(stmt)
        await self.db_session.commit()
        logger.info(f"✓ Cleared pgvector store for tenant {tenant_id}, source {source_id}, type {type}")
