"""
Schema Indexer for extracting metadata from databases and indexing into FAISS.
"""

import logging
import json
import numpy as np
from typing import List, Dict, Any
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.rag.embeddings.service import EmbeddingService
from backend.rag.index.manager import VectorManager

logger = logging.getLogger(__name__)

class SchemaIndexer:
    """Automates the extraction and indexing of database schemas for RAG using FAISS."""
    
    def __init__(self, vector_manager: VectorManager, embedding_service: EmbeddingService):
        self.vector_manager = vector_manager
        self.embedding_service = embedding_service

    async def index_database(self, connection_id: str, engine: AsyncEngine):
        """Extract schema from an engine, embed it, and index it into FAISS."""
        logger.info(f"Indexing schema for connection: {connection_id}")
        
        def get_metadata(connection):
            inspector = inspect(connection)
            schema_info = []
            
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                cols_desc = [f"{c['name']} ({c['type']})" for c in columns]
                
                table_metadata = {
                    "table_name": table_name,
                    "columns": cols_desc,
                    "description": f"Table '{table_name}' with columns: {', '.join(cols_desc)}"
                }
                schema_info.append(table_metadata)
            return schema_info

        async with engine.connect() as conn:
            metadata = await conn.run_sync(get_metadata)

        if not metadata:
            logger.warning(f"No tables found for connection {connection_id}")
            return

        documents = [table['description'] for table in metadata]
        metadatas = []
        for table in metadata:
            metadatas.append({
                "connection_id": connection_id,
                "table_name": table['table_name']
            })

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(documents)} tables...")
        vectors_list = await self.embedding_service.aembed_documents(documents)
        vectors = np.array(vectors_list).astype('float32')

        # Add to FAISS
        self.vector_manager.add_vectors(vectors, metadatas)
        logger.info(f"✓ Indexed {len(metadatas)} tables for {connection_id} into FAISS.")
