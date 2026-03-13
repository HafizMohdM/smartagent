"""
Agent state definition for LangGraph.
This TypedDict flows through every node in the graph, accumulating
the plan, selected tool, execution results, and final response.
"""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """State object that travels through the LangGraph workflow."""

    # The original user query
    user_query: str

    # Current session identifier
    session_id: str

    # Conversation history (list of {"role": ..., "content": ...})
    messages: List[Dict[str, str]]

    # Output of the Planner node
    plan: Dict[str, Any]

    # Tool chosen by the Tool Selector node
    selected_tool: Optional[str]

    # Parameters extracted for the selected tool
    tool_params: Dict[str, Any]

    # Raw result from Tool Execution
    tool_result: Dict[str, Any]

    # Final natural-language response to the user
    final_response: str

    # Iteration counter to prevent infinite loops
    iteration_count: int

    # Whether the evaluator decided the result is satisfactory
    is_complete: bool

    # Context retrieved from the Schema-RAG system
    schema_context: str

    # Error message, if any
    error: Optional[str]
