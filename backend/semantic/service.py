"""
SemanticManager — coordinates the storage and retrieval of business semantics.
Tenant isolated via pgvector. No global state.
"""

import logging
from typing import List, Dict, Any, Optional

from backend.semantic.models import MetricDefinition, EntityDefinition, Relationship
from backend.rag.index.pgvector_manager import PgVectorManager
from backend.rag.embeddings.service import EmbeddingService
from backend.data.pool.engine import vector_async_session_maker

logger = logging.getLogger(__name__)

class SemanticManager:
    """Central service for managing the Semantic Data Layer, strictly isolated by tenant."""
    
    def __init__(self, tenant_id: str, source_id: str):
        self.tenant_id = tenant_id
        self.source_id = source_id
        self.embedding_service = EmbeddingService()

    async def add_metric(self, metric: MetricDefinition):
        """Add a metric to the pgvector store."""
        embedding = await self.embedding_service.aembed_query(
            f"{metric.name}: {metric.description}"
        )
        
        async with vector_async_session_maker() as session:
            rag_svc = PgVectorManager(db_session=session)
            await rag_svc.upsert_embedding(
                tenant_id=self.tenant_id,
                source_id=self.source_id,
                type="metric",
                key=metric.name,
                content=f"{metric.name}: {metric.description}",
                meta_data=metric.model_dump(),
                embedding=embedding
            )
        logger.info(f"✓ Metric '{metric.name}' added for tenant {self.tenant_id}.")

    async def add_entity(self, entity: EntityDefinition):
        """Add an entity to the pgvector store."""
        async with vector_async_session_maker() as session:
            rag_svc = PgVectorManager(db_session=session)
            await rag_svc.upsert_embedding(
                tenant_id=self.tenant_id,
                source_id=self.source_id,
                type="entity",
                key=entity.name,
                content=f"{entity.name}: {entity.description}",
                meta_data=entity.model_dump(),
                embedding=None
            )
        logger.info(f"✓ Entity '{entity.name}' added for tenant {self.tenant_id}.")

    async def add_relationship(self, relationship: Relationship):
        """Add a relationship to the pgvector store."""
        key = f"{relationship.source_entity}_{relationship.target_entity}"
        async with vector_async_session_maker() as session:
            rag_svc = PgVectorManager(db_session=session)
            await rag_svc.upsert_embedding(
                tenant_id=self.tenant_id,
                source_id=self.source_id,
                type="relationship",
                key=key,
                content=key,
                meta_data=relationship.model_dump(),
                embedding=None
            )
        logger.info(f"✓ Relationship '{key}' added for tenant {self.tenant_id}.")

    async def find_metrics(self, query: str, limit: int = 3) -> List[MetricDefinition]:
        """Find the most relevant metrics for a natural language intent."""
        embedding = await self.embedding_service.aembed_query(query)
        
        async with vector_async_session_maker() as session:
            rag_svc = PgVectorManager(db_session=session)
            results = await rag_svc.search_embeddings(
                tenant_id=self.tenant_id,
                source_id=self.source_id,
                type='metric',
                query_embedding=embedding,
                limit=limit
            )
        
        found = []
        for res in results:
            meta = res.get("metadata", {})
            if meta:
                found.append(MetricDefinition(**meta))
        return found

    async def get_all_entities(self) -> Dict[str, EntityDefinition]:
        """Fetch all entities for this tenant and source."""
        async with vector_async_session_maker() as session:
            rag_svc = PgVectorManager(db_session=session)
            results = await rag_svc.get_entities(self.tenant_id, self.source_id)
            
        entities = {}
        for r in results:
            ent = EntityDefinition(**r)
            entities[ent.name] = ent
        return entities

    async def get_all_relationships(self) -> List[Relationship]:
        """Fetch all relationships for this tenant and source."""
        async with vector_async_session_maker() as session:
            rag_svc = PgVectorManager(db_session=session)
            results = await rag_svc.get_relationships(self.tenant_id, self.source_id)
            
        return [Relationship(**r) for r in results]

    async def find_join_path(self, start_entity: str, target_entity: str) -> List[Relationship]:
        """
        BFS to find the shortest join path between two entities in the ERG.
        """
        if start_entity == target_entity:
            return []

        relationships = await self.get_all_relationships()

        queue = [(start_entity, [])]
        visited = {start_entity}

        while queue:
            current, path = queue.pop(0)
            
            for rel in relationships:
                neighbor = None
                if rel.source_entity == current:
                    neighbor = rel.target_entity
                elif rel.target_entity == current:
                    neighbor = rel.source_entity
                
                if neighbor and neighbor not in visited:
                    new_path = path + [rel]
                    if neighbor == target_entity:
                        return new_path
                    visited.add(neighbor)
                    queue.append((neighbor, new_path))
        
        return [] # No path found
