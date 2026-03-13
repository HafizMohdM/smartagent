"""
Semantic Cache Node for the LangGraph workflow.
"""

import logging
from typing import Any, Dict
from backend.agent.state import AgentState
from backend.memory.summary.semantic_cache import SemanticCache
from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

async def cache_node(state: AgentState) -> Dict[str, Any]:
    """
    Checks the semantic cache for a similar query.
    """
    query = state.get("user_query", "")
    logger.info(f"--- CACHE NODE: Checking semantic cache for '{query}' ---")

    try:
        embedding_svc = EmbeddingService()
        cache = SemanticCache(embedding_svc)
        
        cached_res = await cache.lookup(query)
        
        return {
            "cached_result": cached_res
        }
    except Exception as e:
        logger.error(f"Error in cache_node: {e}")
        return {"cached_result": None}
