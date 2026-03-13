"""
Manager for the FAISS vector store and metadata storage.
"""

import os
import faiss
import numpy as np
import pickle
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class VectorManager:
    """Handles the lifecycle and storage of the FAISS vector index and metadata."""
    
    def __init__(self, persist_directory: str = "./faiss_store"):
        self.persist_directory = persist_directory
        self.index_path = os.path.join(persist_directory, "index.faiss")
        self.meta_path = os.path.join(persist_directory, "metadata.pkl")
        
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)
            
        self.index = None
        self.metadata: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load index and metadata from disk if they exist."""
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.meta_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                logger.info(f"✓ Loaded FAISS index and metadata from {self.persist_directory}")
            except Exception as e:
                logger.error(f"✗ Failed to load FAISS store: {e}")
                self._initialize_empty()
        else:
            self._initialize_empty()

    def _initialize_empty(self):
        """Create a new empty index."""
        # Using flat index for small-scale schema RAG (exact search, fast enough)
        # Dimension is 1536 for text-embedding-3-small
        self.index = faiss.IndexFlatL2(1536)
        self.metadata = []
        logger.info("Initialized new empty FAISS index (dimension=1536).")

    def save(self):
        """Persist index and metadata to disk."""
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.meta_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            logger.info(f"✓ FAISS store saved to {self.persist_directory}")
        except Exception as e:
            logger.error(f"✗ Failed to save FAISS store: {e}")

    def add_vectors(self, vectors: np.ndarray, metadatas: List[Dict[str, Any]]):
        """Add vectors and their corresponding metadata to the store."""
        if vectors.dtype != 'float32':
            vectors = vectors.astype('float32')
        
        self.index.add(vectors)
        self.metadata.extend(metadatas)
        self.save()

    def search(self, query_vector: np.ndarray, k: int = 5):
        """Search for the top k nearest neighbors."""
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        if query_vector.dtype != 'float32':
            query_vector = query_vector.astype('float32')
            
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.metadata):
                results.append({
                    "metadata": self.metadata[idx],
                    "distance": float(dist)
                })
        return results

    def clear(self):
        """Wipe the store."""
        self._initialize_empty()
        self.save()
