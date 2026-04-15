"""
Retriever service for fetching relevant schema context using FAISS.
"""

import logging
import numpy as np
from typing import List, Dict, Any
from backend.rag.index.manager import VectorManager
from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

class SchemaRetriever:
    """Retrieves relevant database schema metadata using FAISS and embeddings."""
    
    def __init__(self, vector_manager: VectorManager, embedding_service: EmbeddingService):
        self.vector_manager = vector_manager
        self.embedding_service = embedding_service

    async def retrieve_relevant_schemas(self, query: str, limit: int = 5) -> str:
        """
        Query FAISS for relevant tables and format them into a context string.
        """
        logger.info(f"Retrieving schemas for query: {query}")
        
        try:
            # 1. Embed the query
            query_vector_list = await self.embedding_service.aembed_query(query)
            query_vector = np.array(query_vector_list).astype('float32')
            
            # 2. Search FAISS
            results = self.vector_manager.search(query_vector, k=limit)
            
            if not results:
                return "No relevant database schemas found."

            # 3. Format results
            context_parts = []
            for res in results:
                meta = res['metadata']
                # Reconstructing description-like context (or we could store desc in meta)
                # For now we'll just indicate the table name
                context_parts.append(f"Table: {meta['table_name']} (Connection: {meta['connection_id']})")
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            logger.exception(f"Error during schema retrieval: {e}")
            return f"Error retrieving schema context: {str(e)}"
