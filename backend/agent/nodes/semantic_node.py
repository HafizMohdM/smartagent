"""
Semantic Node — Retrieves metrics, entity metadata, and join paths to ground the agent in business logic.
Tenant isolated via pgvector.
"""

import logging
from typing import Dict, Any
from backend.agent.state import AgentState
from backend.rag.index.pgvector_manager import PgVectorManager
from backend.data.pool.engine import vector_async_session_maker
from backend.rag.embeddings.service import EmbeddingService
import json
import asyncio

logger = logging.getLogger(__name__)

async def semantic_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves semantic context for the current query using tenant-isolated pgvector."""
    user_query = state.get("user_query", "")
    tenant_id = state.get("tenant_id")
    connection_id = state.get("connection_id")
    
    # MANDATORY VALIDATION GATE
    if not tenant_id or not connection_id:
        logger.error("[RAG] ISOLATION VIOLATION: tenant_id or connection_id missing from state")
        return {"schema_context": "", "error": "Missing tenant context"}
    
    try:
        async def fetch_context():
            embedding_svc = EmbeddingService()
            query_vec = await embedding_svc.aembed_query(user_query)
            
            async with vector_async_session_maker() as rag_session:
                rag_svc = PgVectorManager(db_session=rag_session)
                
                # 1. Retrieve Relevant Metrics (Semantic Search)
                metrics = await rag_svc.search_embeddings(
                    tenant_id=tenant_id, source_id=connection_id,
                    type='metric', query_embedding=query_vec, limit=5
                )
                
                # 2. Identify Potential Entities (Keyword matching)
                all_entities = await rag_svc.get_entities(tenant_id, connection_id)
                entities_involved = []
                for ent_def in all_entities:
                    ent_name = ent_def.get("name", "")
                    if ent_name.lower() in user_query.lower():
                        entities_involved.append(ent_name)
                
                # 3. Build Semantic Context String
                metric_context = ""
                for m in metrics:
                    meta = m.get("metadata", {})
                    name = meta.get("name", "Unknown Metric")
                    desc = meta.get("description", "")
                    sql = meta.get("sql_snippet", "")
                    metric_context += f"- {name}: {desc} | Formula: {sql}\n"
                
                semantic_context = (
                    "### BUSINESS METRICS FOUND:\n" + (metric_context if metric_context else "None found - use best judgment.") +
                    "\n\n### IDENTIFIED ENTITIES:\n" + (", ".join(entities_involved) if entities_involved else "None directly identified.")
                )
                
                return semantic_context

        # Add timeout to prevent vector search from hanging the graph
        semantic_context = await asyncio.wait_for(fetch_context(), timeout=4.0)
        
        logger.info(f"Retrieved semantic context for tenant {tenant_id}, source {connection_id}.")
        return {"schema_context": semantic_context, "error": None}
        
    except asyncio.TimeoutError:
        logger.warning(f"[RAG] Timeout fetching semantic context for tenant {tenant_id}")
        return {"schema_context": "", "error": None}
    except Exception as e:
        logger.error(f"[RAG] Failed to fetch semantic context: {e}", exc_info=True)
        return {"schema_context": "", "error": None}
