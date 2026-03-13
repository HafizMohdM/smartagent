"""
Semantic Node — replaces or enhances the original Schema-RAG node.
Retrieves metrics, entity metadata, and join paths to ground the agent in business logic.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.agent.state import AgentState
from backend.semantic.service import SemanticManager

logger = logging.getLogger(__name__)

async def semantic_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves semantic context for the current query."""
    user_query = state.get("user_query", "")
    manager = SemanticManager()
    
    # 1. Retrieve Relevant Metrics (Semantic Search)
    metrics = await manager.find_metrics(user_query, limit=5)
    
    # 2. Identify Potential Entities (Simplified keyword matching for now)
    entities_involved = []
    for ent_name, ent_def in manager.entities.items():
        if ent_name.lower() in user_query.lower():
            entities_involved.append(ent_name)
    
    # 3. Discover Join Paths if multiple entities identified
    join_paths_description = ""
    if len(entities_involved) >= 2:
        path = manager.find_join_path(entities_involved[0], entities_involved[1])
        if path:
            join_paths_description = "\nRecommended JOIN paths:\n"
            for rel in path:
                join_paths_description += f"- {rel.source_entity} -> {rel.target_entity} ({rel.join_on})\n"

    # 4. Build Semantic Context String
    metric_context = "\n".join([f"- {m.name}: {m.description} | Formula: {m.sql_snippet}" for m in metrics])
    
    semantic_context = (
        "### BUSINESS METRICS FOUND:\n" + (metric_context if metrics else "None found - use best judgment.") +
        "\n\n### IDENTIFIED ENTITIES:\n" + (", ".join(entities_involved) if entities_involved else "None directly identified.") +
        join_paths_description
    )

    logger.info(f"Retrieved semantic context: {len(metrics)} metrics, {len(entities_involved)} entities.")
    
    return {
        "schema_context": semantic_context, # We reuse the schema_context key for now to minimize state changes
        "error": None
    }
