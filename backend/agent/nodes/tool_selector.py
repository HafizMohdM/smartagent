
"""
Tool Selection Node — routes to the correct tool based on the planner's output.
"""

import logging
from typing import Any, Dict

from backend.agent.state import AgentState
from backend.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def tool_selector_node(state: AgentState) -> Dict[str, Any]:
    """Select the tool specified by the plan and validate it exists."""
    plan = state.get("plan", {})
    tool_name = plan.get("tool", "none")
    tool_params = plan.get("parameters", {})

    if tool_name == "none":
        logger.info("No tool required — passing to evaluator with direct response.")
        return {
            "selected_tool": None,
            "tool_params": {},
            "tool_result": {
                "success": True,
                "data": None,
                "message": "No tool needed for this query.",
            },
        }

    registry = ToolRegistry()
    tool = registry.get(tool_name)

    if tool is None:
        available = registry.list_tool_names()
        logger.warning(
            f"Tool '{tool_name}' not found. Available: {available}"
        )
        return {
            "selected_tool": None,
            "tool_params": {},
            "tool_result": {
                "success": False,
                "error": f"Tool '{tool_name}' is not available. Available tools: {available}",
            },
        }

    logger.info(f"Tool selected: {tool_name} with params: {tool_params}")
    return {
        "selected_tool": tool_name,
        "tool_params": tool_params,
    }
