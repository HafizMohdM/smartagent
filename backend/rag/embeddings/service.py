"""
Embedding Service logic for generating vector representations of schemas.
"""

from typing import List, Optional
import logging
from langchain_openai import OpenAIEmbeddings
from backend.config.settings import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Manages embedding generation for schema indexing and retrieval."""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        self.embeddings = OpenAIEmbeddings(
            model=model,
            openai_api_key=settings.OPENAI_API_KEY
        )
        logger.debug(f"Initialised EmbeddingService with model: {model}")

    async def aembed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        return await self.embeddings.aembed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of documents."""
        return await self.embeddings.aembed_documents(texts)
