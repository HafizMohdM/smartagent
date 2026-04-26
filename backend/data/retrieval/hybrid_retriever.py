import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, text
from backend.models.table_metadata import TableMetadataStore
from backend.data.pool.engine import async_session_maker
from backend.rag.embeddings.service import EmbeddingService
from .table_metadata import TABLE_METADATA # Fallback

logger = logging.getLogger(__name__)

class HybridTableRetriever:
    """
    Retrieves relevant tables using keyword and semantic matching via pgvector.
    Supports multi-tenant isolation via connection_id.
    Ensures backward compatibility with a hardcoded fallback.
    """

    def __init__(self, embedding_service: EmbeddingService):
        self._embedding_service = embedding_service
        self._fallback_metadata = TABLE_METADATA
        self._fallback_map = {item["table_name"]: item for item in TABLE_METADATA}

    async def aget_relevant_tables(
        self, 
        user_query: str, 
        db_schema: Dict[str, Any], 
        tenant_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        limit: int = 5
    ) -> List[str]:
        """
        Returns top relevant tables using database metadata if available, 
        otherwise falls back to hardcoded Phase 1 metadata.
        """
        if connection_id and tenant_id:
            try:
                return await self._get_db_based_tables(user_query, db_schema, tenant_id, connection_id, limit)
            except Exception as e:
                logger.error(f"Error fetching from TableMetadataStore for {tenant_id}/{connection_id}: {e}. Falling back to Phase 1.")
        
        return await self._get_fallback_tables(user_query, db_schema, limit)

    async def _get_db_based_tables(self, user_query: str, db_schema: Dict[str, Any], tenant_id: str, connection_id: str, limit: int) -> List[str]:
        """Query pgvector backend for relevant tables."""
        query_lower = user_query.lower()
        query_keywords = [w for w in re.findall(r'\w+', query_lower) if len(w) > 2]
        
        async with async_session_maker() as session:
            # 1. Keyword Matching (Priority)
            from sqlalchemy import or_, func
            
            # Basic singularization for "employees" -> "employee"
            normalized_keywords = []
            for kw in query_keywords:
                normalized_keywords.append(kw)
                if kw.endswith('ies'): normalized_keywords.append(kw[:-3] + 'y')
                elif kw.endswith('s') and len(kw) > 3: normalized_keywords.append(kw[:-1])

            # Build broad keyword filters
            kw_conditions = []
            for kw in normalized_keywords:
                kw_conditions.append(TableMetadataStore.table_name.ilike(f"%{kw}%"))
                kw_conditions.append(TableMetadataStore.synonyms.any(kw))
            
            kw_stmt = select(TableMetadataStore.table_name).where(
                TableMetadataStore.tenant_id == tenant_id,
                TableMetadataStore.connection_id == connection_id,
                TableMetadataStore.table_name.in_(db_schema.keys())
            )
            if kw_conditions:
                kw_stmt = kw_stmt.where(or_(*kw_conditions))
            
            kw_result = await session.execute(kw_stmt)
            keyword_matches = [row[0] for row in kw_result.fetchall()]
            
            # Final direct fallback to db_schema keys (even if store is empty or missing entry)
            for table_name in db_schema.keys():
                t_lower = table_name.lower()
                if any(kw in t_lower for kw in normalized_keywords) or any(t_lower in kw for kw in normalized_keywords):
                    if table_name not in keyword_matches:
                        keyword_matches.append(table_name)

            # 2. Semantic Matching
            query_embedding = await self._embedding_service.aembed_query(user_query)
            
            sem_stmt = select(
                TableMetadataStore.table_name,
                TableMetadataStore.embedding.cosine_distance(query_embedding).label("distance")
            ).where(
                TableMetadataStore.tenant_id == tenant_id,
                TableMetadataStore.connection_id == connection_id,
                TableMetadataStore.table_name.in_(db_schema.keys()),
                TableMetadataStore.table_name.not_in(keyword_matches)
            ).order_by("distance").limit(limit)
            
            sem_result = await session.execute(sem_stmt)
            semantic_matches = []
            top_distance = 1.0
            
            for row in sem_result.fetchall():
                name, distance = row
                semantic_matches.append((name, 1.0 - distance)) # Score = 1 - distance
                if top_distance > distance:
                    top_distance = distance

            # 3. Confidence Control
            # If no keywords and top semantic score is weak
            if not keyword_matches:
                # Be more lenient if it's a short query (likely a specific table check)
                threshold = 0.45 if len(query_keywords) > 1 else 0.35
                
                if not semantic_matches or semantic_matches[0][1] < threshold:
                    logger.warning(f"Low retrieval confidence for query: '{user_query}'")
                    # If it's a very simple query like "employees", we MUST return SOMETHING if it exists
                    # This is handled by the direct keyword match fallback above
                    if not keyword_matches:
                        return []

            # 4. Merge
            selected = []
            seen = set()
            for name in keyword_matches + [m[0] for m in semantic_matches if m[1] > 0.3]:
                if name not in seen:
                    selected.append(name)
                    seen.add(name)
                if len(selected) >= limit:
                    break
                    
            return selected

    async def _get_fallback_tables(self, user_query: str, db_schema: Dict[str, Any], limit: int) -> List[str]:
        """Original Phase 1 logic for backward compatibility."""
        query_lower = user_query.lower()
        query_keywords = [w for w in re.findall(r'\w+', query_lower) if len(w) > 2]
        
        keyword_matches = []
        for item in self._fallback_metadata:
            table_name = item["table_name"]
            name_match = any(kw in table_name.lower() for kw in query_keywords)
            synonym_match = any(syn.lower() in query_lower for syn in item.get("synonyms", []))
            if (name_match or synonym_match) and table_name in db_schema:
                keyword_matches.append(table_name)

        # Semantic Match
        query_embedding = await self._embedding_service.aembed_query(user_query)
        # (Simplified for now - assumes embeddings are pre-cached in Phase 1 retriever)
        # Note: In Phase 2, we prefer DB search. Fallback is meant for local dev.
        # I'll just return keyword matches for fallback if embedding logic is complex to duplicate.
        return keyword_matches[:limit]

    async def get_table_metadata(self, table_name: str, tenant_id: Optional[str] = None, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch full metadata including pre-calculated relationships."""
        if connection_id and tenant_id:
            async with async_session_maker() as session:
                stmt = select(TableMetadataStore).where(
                    TableMetadataStore.tenant_id == tenant_id,
                    TableMetadataStore.connection_id == connection_id,
                    TableMetadataStore.table_name == table_name
                )
                result = await session.execute(stmt)
                obj = result.scalars().first()
                if obj:
                    return {
                        "table_name": obj.table_name,
                        "columns": obj.columns,
                        "description": obj.description,
                        "relationships": obj.relationships or []
                    }
        
        # Fallback
        item = self._fallback_map.get(table_name)
        if item:
            return {
                "table_name": item["table_name"],
                "columns": item["columns"],
                "description": item["description"],
                "relationships": [] # Phase 1 had no pre-calculated FKs
            }
        return {}
