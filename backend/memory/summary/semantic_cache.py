"""
Semantic Cache for storing and retrieving previously successful query results.
"""

import logging
import numpy as np
from typing import Optional, Dict, Any
from backend.rag.index.manager import VectorManager
from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

class SemanticCache:
    """Provides vector-similarity based caching for natural language queries."""
    
    def __init__(self, embedding_service: EmbeddingService, threshold: float = 0.15):
        # Initialise with a dedicated directory for cache
        self.vector_manager = VectorManager(store_name="semantic_cache")
        self.embedding_service = embedding_service
        self.threshold = threshold # L2 distance threshold for "hit"

    async def lookup(self, query: str) -> Optional[Dict[str, Any]]:
        """Check if a similar query exists in cache."""
        try:
            query_vector_list = await self.embedding_service.aembed_query(query)
            query_vector = np.array(query_vector_list).astype('float32')
            
            results = self.vector_manager.search(query_vector, k=1)
            
            if results:
                hit = results[0]
                # Lower distance = more similar
                if hit['distance'] < self.threshold:
                    logger.info(f"⚡ Semantic cache HIT (dist={hit['distance']:.4f})")
                    return hit['metadata']['result']
                else:
                    logger.debug(f"Semantic cache MISS (closest dist={hit['distance']:.4f})")
            
            return None
        except Exception as e:
            logger.error(f"Error in semantic cache lookup: {e}")
            return None

    async def update(self, query: str, result: Dict[str, Any]):
        """Save a new successful result to the semantic cache."""
        try:
            query_vector_list = await self.embedding_service.aembed_query(query)
            vector = np.array([query_vector_list]).astype('float32')
            
            metadata = [{
                "query": query,
                "result": result
            }]
            
            self.vector_manager.add_vectors(vector, metadata)
            logger.info(f"✓ Semantic cache updated for: {query[:50]}...")
        except Exception as e:
            logger.error(f"Error updating semantic cache: {e}")
