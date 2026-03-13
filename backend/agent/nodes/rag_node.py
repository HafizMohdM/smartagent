"""
LangGraph Node for the Schema-RAG step using FAISS.
"""

import logging
from typing import Any, Dict
from backend.agent.state import AgentState
from backend.rag.retriever.schema_retriever import SchemaRetriever
from backend.rag.index.manager import VectorManager
from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

async def rag_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieves relevant database schemas based on the current user query
    and adds them to the agent state as 'schema_context'.
    """
    query = state.get("user_query", "") # State key is user_query in AgentState
    logger.info(f"--- RAG NODE: Retrieving context for '{query}' ---")

    try:
        # Initialise services
        vector_mgr = VectorManager()
        embedding_svc = EmbeddingService()
        retriever = SchemaRetriever(vector_mgr, embedding_svc)
        
        context = await retriever.retrieve_relevant_schemas(query)
        
        return {
            "schema_context": context,
            "messages": state.get("messages", []) + [
                {"role": "system", "content": "Retrieved relevant schema context."}
            ]
        }
    except Exception as e:
        logger.error(f"Error in rag_node: {e}")
        return {
            "schema_context": f"Error retrieving context: {str(e)}",
            "error": str(e)
        }
