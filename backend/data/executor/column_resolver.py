"""
Embedding-Based Column Resolver — resolves vague column references using vector similarity.

When regex-based synonym resolution fails (e.g., a schema uses "personnel_given_nm"
for first name), this resolver falls back to cosine similarity against column embeddings
stored in TableMetadataStore.

Leverages the existing EmbeddingService (OpenAI text-embedding-3-small) and
caches column embeddings to minimize API calls.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

# Minimum cosine similarity to accept a column match
DEFAULT_SIMILARITY_THRESHOLD = 0.72


def _col_name(col: Any) -> str:
    """Extract column name from either a dict or a plain string."""
    if isinstance(col, dict):
        return col.get("name", "")
    return str(col)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class EmbeddingColumnResolver:
    """
    Resolves vague column references using vector similarity.

    Workflow:
      1. Embed the user's column term (e.g., "first name")
      2. Compare against cached column embeddings (e.g., "personnel_given_nm")
      3. Return the best match above the similarity threshold

    Column embeddings are cached in-memory per connection_id to avoid
    redundant API calls within a session.
    """

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self._embedding_service = embedding_service or EmbeddingService()
        # Cache: connection_id → {col_name → embedding_vector}
        self._column_embedding_cache: Dict[str, Dict[str, List[float]]] = {}

    async def resolve_column(
        self,
        user_term: str,
        schema: Dict[str, Any],
        connection_id: Optional[str] = None,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> Optional[str]:
        """
        Find the most semantically similar column name in the schema.

        Args:
            user_term:     The user's vague column reference (e.g., "first name")
            schema:        The database schema dict.
            connection_id: Optional connection ID for caching.
            threshold:     Minimum cosine similarity to accept a match.

        Returns:
            The best matching column name, or None if no match exceeds threshold.

        Example:
            "first name" → cosine_sim → "personnel_given_nm" (0.82) → match
        """
        if not user_term or not schema:
            return None

        # 1. Get all column names from schema
        all_columns = self._extract_all_columns(schema)
        if not all_columns:
            return None

        # 2. Get or build column embeddings
        col_embeddings = await self._get_column_embeddings(
            all_columns, connection_id
        )
        if not col_embeddings:
            return None

        # 3. Embed the user term
        try:
            term_embedding = await self._embedding_service.aembed_query(user_term)
        except Exception as e:
            logger.warning(f"Failed to embed user term '{user_term}': {e}")
            return None

        # 4. Find best match by cosine similarity
        best_col = None
        best_score = 0.0

        for col_name, col_embedding in col_embeddings.items():
            score = _cosine_similarity(term_embedding, col_embedding)
            if score > best_score:
                best_score = score
                best_col = col_name

        if best_score >= threshold and best_col:
            logger.info(
                f"Column resolved: '{user_term}' → '{best_col}' "
                f"(similarity={best_score:.3f})"
            )
            return best_col

        logger.debug(
            f"No column match for '{user_term}' above threshold "
            f"(best='{best_col}', score={best_score:.3f}, threshold={threshold})"
        )
        return None

    async def resolve_columns_batch(
        self,
        terms: List[str],
        schema: Dict[str, Any],
        connection_id: Optional[str] = None,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> Dict[str, Optional[str]]:
        """
        Batch resolution for multiple terms.

        Returns:
            Dict mapping each term to its best matching column (or None).
        """
        results: Dict[str, Optional[str]] = {}
        for term in terms:
            results[term] = await self.resolve_column(
                term, schema, connection_id, threshold
            )
        return results

    async def _get_column_embeddings(
        self,
        all_columns: List[str],
        connection_id: Optional[str] = None,
    ) -> Dict[str, List[float]]:
        """
        Build or retrieve cached column embeddings.

        Generates descriptive text for each column name, then embeds it.
        Caches per connection_id for session reuse.
        """
        cache_key = connection_id or "_default"

        # Check cache
        cached = self._column_embedding_cache.get(cache_key)
        if cached and set(cached.keys()) == set(all_columns):
            return cached

        # Generate embeddings for each column
        # We create descriptive text to improve embedding quality
        col_texts = []
        for col in all_columns:
            # Convert column name to natural language for better embedding
            readable = col.replace("_", " ").replace("-", " ").strip()
            col_texts.append(f"Database column: {readable} ({col})")

        try:
            embeddings = await self._embedding_service.aembed_documents(col_texts)
        except Exception as e:
            logger.error(f"Failed to embed columns: {e}")
            return {}

        col_embeddings = dict(zip(all_columns, embeddings))

        # Cache
        self._column_embedding_cache[cache_key] = col_embeddings
        logger.info(
            f"Cached {len(col_embeddings)} column embeddings "
            f"for connection {cache_key}"
        )

        return col_embeddings

    def _extract_all_columns(self, schema: Dict[str, Any]) -> List[str]:
        """Extract all unique column names from the schema."""
        seen = set()
        columns = []
        for table_info in schema.values():
            for col in table_info.get("columns", []):
                cn = _col_name(col)
                if cn and cn not in seen:
                    columns.append(cn)
                    seen.add(cn)
        return columns

    def invalidate_cache(self, connection_id: Optional[str] = None) -> None:
        """Clear column embedding cache for a connection (or all)."""
        if connection_id:
            self._column_embedding_cache.pop(connection_id, None)
        else:
            self._column_embedding_cache.clear()

    async def preload_cache(
        self,
        schema: Dict[str, Any],
        connection_id: str,
    ) -> int:
        """
        Pre-generate and cache column embeddings for a connection.
        Call this during schema sync to avoid cold-start latency.

        Returns:
            Number of columns cached.
        """
        all_columns = self._extract_all_columns(schema)
        col_embeddings = await self._get_column_embeddings(
            all_columns, connection_id
        )
        return len(col_embeddings)
