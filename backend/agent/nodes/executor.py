"""
Executor Node — calls the selected tool and captures the result.
"""

import logging
import traceback
from typing import Any, Dict

from backend.agent.state import AgentState
from backend.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def executor_node(state: AgentState) -> Dict[str, Any]:
    """Execute the selected tool and return the result."""
    tool_name = state.get("selected_tool")
    tool_params = state.get("tool_params", {})
    session_id = state.get("session_id", "")

    # If no tool was selected (e.g., conversational query), skip execution
    if tool_name is None:
        return {
            "tool_result": state.get("tool_result", {
                "success": True,
                "data": None,
                "message": "No tool execution required.",
            }),
        }

    registry = ToolRegistry()
    tool = registry.get(tool_name)

    if tool is None:
        return {
            "tool_result": {
                "success": False,
                "error": f"Tool '{tool_name}' not found in registry.",
            }
        }

    try:
        logger.info(f"Executing tool: {tool_name}")
        result = await tool.execute(params=tool_params, session_id=session_id)
        logger.info(f"Tool '{tool_name}' completed. success={result.success}")
        return {
            "tool_result": result.model_dump(),
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {e}\n{traceback.format_exc()}")
        return {
            "tool_result": {
                "success": False,
                "error": f"Tool execution error: {str(e)}",
            }
        }
