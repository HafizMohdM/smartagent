"""
LangGraph Agent Orchestrator.
Builds a stateful graph: Planner → Tool Selector → Executor → Evaluator
with conditional retry edges. This is the central brain of the platform.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes import (
    planner_node,
    tool_selector_node,
    executor_node,
    evaluator_node,
    semantic_node
)
from backend.memory.session.manager import SessionManager

logger = logging.getLogger(__name__)


def _should_retry(state: AgentState) -> str:
    """Conditional edge: route back to planner on retry, or finish."""
    if state.get("is_complete", True):
        return "end"
    
    # Bounded retry logic
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) reached in graph edge. Terminating.")
        return "end"
        
    return "planner"


def build_agent_graph() -> StateGraph:
    """Construct the LangGraph state graph for agent orchestration with Semantic SDL."""
    graph = StateGraph(AgentState)

    # ── Add nodes ──────────────────────────────────────────────────
    graph.add_node("semantic", semantic_node)
    graph.add_node("planner", planner_node)
    graph.add_node("tool_selector", tool_selector_node)
    graph.add_node("executor", executor_node)
    graph.add_node("evaluator", evaluator_node)

    # ── Define edges ───────────────────────────────────────────────
    graph.set_entry_point("semantic")
    graph.add_edge("semantic", "planner")
    graph.add_edge("planner", "tool_selector")
    graph.add_edge("tool_selector", "executor")
    graph.add_edge("executor", "evaluator")

    # Conditional: evaluator → END or evaluator → planner (retry)
    graph.add_conditional_edges(
        "evaluator",
        _should_retry,
        {
            "end": END,
            "planner": "planner",
        },
    )

    return graph


class AgentOrchestrator:
    """
    High-level interface to the LangGraph agent.
    Manages session memory and invokes the compiled graph.
    """

    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager
        self._graph = build_agent_graph().compile()
        logger.info("AgentOrchestrator initialised with compiled graph.")

    async def run(
        self,
        query: str,
        session_id: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user query through the full agent pipeline.

        Args:
            query:      Natural-language user query.
            session_id: Active session identifier.
            history:    Optional conversation history.

        Returns:
            Dict with 'response', 'tool_used', and 'plan'.
        """
        # Persist user message
        await self._session_manager.add_message(session_id, "user", query)

        # Retrieve history if not provided
        if history is None:
            history = await self._session_manager.get_history(session_id)

        initial_state: AgentState = {
            "user_query": query,
            "session_id": session_id,
            "messages": history,
            "plan": {},
            "selected_tool": None,
            "tool_params": {},
            "tool_result": {},
            "final_response": "",
            "is_complete": False,
            "schema_context": "",
            "retry_count": 0,
            "token_usage": 0,
            "execution_count": 0,
            "max_retries": 3, # Enterprise SLA: Max 3 retries
            "error": None,
            "trace_id": f"tr_{session_id}_{int(time.time())}",
            "node_telemetry": {},
        }

        logger.info(f"Running agent for session {session_id}: {query[:80]}...")
        result = await self._graph.ainvoke(initial_state)  # type: ignore

        response_text = result.get("final_response", "I could not process your request.")

        # Persist assistant response
        await self._session_manager.add_message(session_id, "assistant", response_text)

        return {
            "response": response_text,
            "tool_used": result.get("selected_tool"),
            "plan": result.get("plan", {}),
            "generated_sql": result.get("tool_params", {}).get("sql"),
            "tool_result": result.get("tool_result"),
        }
