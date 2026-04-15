"""
Executor Node — calls the selected tool and captures the result.
"""

import logging
import traceback
from typing import Any, Dict

from backend.agent.state import AgentState
from backend.agent.tools.registry import ToolRegistry

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

    # ── Pre-execution Validation (for SQL) ─────────────────────────
    if tool_name == "database_query" and "sql" in tool_params:
        from backend.agent.tools.sql_validator import SQLValidator
        validator = SQLValidator()
        validation = validator.validate(tool_params["sql"])
        
        if not validation["is_valid"]:
            logger.warning(f"SQL validation failed: {validation['reason']}")
            return {
                "tool_result": {
                    "success": False,
                    "error": f"PRE_EXECUTION_VALIDATION_FAILED: {validation['reason']}",
                }
            }

    try:
        logger.info(f"Executing tool: {tool_name}")
        result = await tool.execute(params=tool_params, session_id=session_id)
        
        # Track execution count
        execution_count = state.get("execution_count", 0) + 1
        
        logger.info(f"Tool '{tool_name}' completed. success={result.success}")
        return {
            "tool_result": result.model_dump(),
            "execution_count": execution_count,
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {e}\n{traceback.format_exc()}")
        return {
            "tool_result": {
                "success": False,
                "error": f"Tool execution error: {str(e)}",
            }
        }
