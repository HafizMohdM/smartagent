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
    semantic_node,
    summarizer_node,
    chart_node
)
from backend.memory.session.manager import SessionManager
from backend.agent.utils.sql_parser import SQLParser

logger = logging.getLogger(__name__)


def _should_retry(state: AgentState) -> str:
    """Conditional edge: route back to planner on retry, or finish."""
    if state.get("is_complete", True):
        return "summarizer"
    
    # Bounded retry logic
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) reached in graph edge. Terminating.")
        return "summarizer"
        
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
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("chart", chart_node)

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
            "summarizer": "summarizer",
            "planner": "planner",
        },
    )

    graph.add_edge("summarizer", "chart")
    graph.add_edge("chart", END)

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

        # Prioritize the fully formatted response (Table + Summary)
        final_resp = result.get("final_response")
        summary = result.get("summary")
        response_text = final_resp or summary or "I could not process your request."

        # Inject user_query into tool_result metadata for persistence
        if "tool_result" in result and result["tool_result"]:
            if "metadata" not in result["tool_result"] or result["tool_result"]["metadata"] is None:
                result["tool_result"]["metadata"] = {}
            result["tool_result"]["metadata"]["user_query"] = result.get("user_query")

        # Persist assistant response
        await self._session_manager.add_message(session_id, "assistant", response_text)

        # Requirement 1: Extract pure SQL and ensure it's not in the summary
        # If any node populated 'generated_sql', use it. Otherwise, extract from the LLM's raw output if available.
        raw_sql = result.get("generated_sql") or result.get("sql", "")
        pure_sql = SQLParser.extract_sql(raw_sql) or (raw_sql if SQLParser.is_executable(raw_sql) else None)

        return {
            "summary": response_text,
            "sql": pure_sql,
            "preview_rows": result.get("preview_rows", []),
            "metadata": {
                **result.get("metadata", {}),
                "user_query": result.get("user_query"),
                "generated_sql": pure_sql,
                "data": result.get("tool_result", {}).get("data")
            },
            "chart": result.get("chart_config", {}),
            # Legacy fields for potential backward compatibility
            "response": response_text,
            "tool_used": result.get("selected_tool"),
            "plan": result.get("plan", {}),
            "tool_result": result.get("tool_result"),
        }
