import logging
import numpy as np
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.knowledge_base_chunk import KnowledgeBaseChunk

logger = logging.getLogger(__name__)

class PgVectorManager:
    """Handles the lifecycle and storage of pgvector-based embeddings scoped to a Tenant."""
    
    def __init__(self, db_session: Session, tenant_id: UUID):
        self.db_session = db_session
        self.tenant_id = tenant_id

    def add_vectors(self, document_id: UUID, vectors: List[List[float]], texts: List[str]):
        """Add embeddings and their corresponding text for a specific document."""
        if len(vectors) != len(texts):
            raise ValueError("Number of vectors must match number of texts")
            
        chunks = []
        for i, vector in enumerate(vectors):
            chunk = KnowledgeBaseChunk(
                tenant_id=self.tenant_id,
                document_id=document_id,
                content=texts[i],
                embedding=vector
            )
            chunks.append(chunk)
            
        self.db_session.add_all(chunks)
        self.db_session.commit()
        logger.info(f"✓ Added {len(chunks)} vectors to pgvector for document {document_id}")

    def search(self, query_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Search for the top k nearest neighbors using pgvector L2 distance."""
        # Ensure query_vector is a list of floats
        if isinstance(query_vector, np.ndarray):
            query_vector = query_vector.tolist()
            
        stmt = (
            select(KnowledgeBaseChunk)
            .where(KnowledgeBaseChunk.tenant_id == self.tenant_id)
            .order_by(KnowledgeBaseChunk.embedding.l2_distance(query_vector))
            .limit(k)
        )
        
        results = self.db_session.execute(stmt).scalars().all()
        
        # Format similar to what the previous VectorManager returned
        formatted_results = []
        for row in results:
            formatted_results.append({
                "metadata": {
                    "document_id": str(row.document_id),
                    "text": row.content,
                },
                "content": row.content
            })
            
        return formatted_results

    def clear(self):
        """Wipe the store for this tenant."""
        stmt = select(KnowledgeBaseChunk).where(KnowledgeBaseChunk.tenant_id == self.tenant_id)
        chunks = self.db_session.execute(stmt).scalars().all()
        for chunk in chunks:
            self.db_session.delete(chunk)
        self.db_session.commit()
        logger.info(f"✓ Cleared pgvector store for tenant {self.tenant_id}")
