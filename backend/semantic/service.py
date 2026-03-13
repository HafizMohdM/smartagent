"""
SemanticManager — coordinates the storage and retrieval of business semantics.
Uses FAISS for semantic metric lookup and local storage for entity relationships.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import numpy as np

from backend.semantic.models import MetricDefinition, EntityDefinition, Relationship
from backend.rag.index.manager import VectorManager
from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

class SemanticManager:
    """Central service for managing the Semantic Data Layer."""
    
    def __init__(self, base_path: str = "./vector_store/semantic"):
        self.base_path = base_path
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            
        # Vector store for searching metrics by description/intent
        self.vector_manager = VectorManager(store_name="metrics", base_path="./vector_store")
        self.embedding_service = EmbeddingService()
        
        # Structured stores for entities and relationships
        self.metrics_data_path = os.path.join(base_path, "metrics.json")
        self.entities_path = os.path.join(base_path, "entities.json")
        self.relationships_path = os.path.join(base_path, "relationships.json")
        
        self.metrics: Dict[str, MetricDefinition] = self._load_data(self.metrics_data_path, MetricDefinition)
        self.entities: Dict[str, EntityDefinition] = self._load_data(self.entities_path, EntityDefinition)
        self.relationships: List[Relationship] = self._load_list(self.relationships_path, Relationship)

    def _load_data(self, path, model_cls) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return {k: model_cls(**v) for k, v in data.items()}
        return {}

    def _load_list(self, path, model_cls) -> List[Any]:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return [model_cls(**v) for v in data]
        return []

    def _save_all(self):
        """Persist structured data to disk."""
        with open(self.metrics_data_path, 'w') as f:
            json.dump({k: v.model_dump() for k, v in self.metrics.items()}, f, indent=2)
        with open(self.entities_path, 'w') as f:
            json.dump({k: v.model_dump() for k, v in self.entities.items()}, f, indent=2)
        with open(self.relationships_path, 'w') as f:
            json.dump([v.model_dump() for v in self.relationships], f, indent=2)

    async def add_metric(self, metric: MetricDefinition):
        """Add a metric to the registry and index its description for vector search."""
        self.metrics[metric.name] = metric
        
        # Index for semantic search
        embedding = await self.embedding_service.get_embeddings(
            f"{metric.name}: {metric.description}"
        )
        self.vector_manager.add_vectors(
            np.array([embedding]),
            [{"name": metric.name, "type": "metric"}]
        )
        self._save_all()
        logger.info(f"✓ Metric '{metric.name}' added and indexed.")

    async def find_metrics(self, query: str, limit: int = 3) -> List[MetricDefinition]:
        """Find the most relevant metrics for a natural language intent."""
        embedding = await self.embedding_service.get_embeddings(query)
        results = self.vector_manager.search(np.array(embedding), k=limit)
        
        found = []
        for res in results:
            metric_name = res["metadata"]["name"]
            if metric_name in self.metrics:
                found.append(self.metrics[metric_name])
        return found

    def get_entity_graph(self) -> Dict[str, Any]:
        """Return the ERG for pathfinding."""
        return {
            "entities": self.entities,
            "relationships": self.relationships
        }

    def find_join_path(self, start_entity: str, target_entity: str) -> List[Relationship]:
        """
        BFS to find the shortest join path between two entities in the ERG.
        """
        if start_entity == target_entity:
            return []

        queue = [(start_entity, [])]
        visited = {start_entity}

        while queue:
            current, path = queue.pop(0)
            
            # Find all relationships where 'current' is source or target
            for rel in self.relationships:
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
