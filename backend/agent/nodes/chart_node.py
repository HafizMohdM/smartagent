"""
Chart Node — analyzes tools results to generate automatic chart data.
"""

import logging
from typing import Any, Dict

from backend.agent.state import AgentState
from backend.agent.utils.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)

async def chart_node(state: AgentState) -> Dict[str, Any]:
    """
    Creates a chart configuration for the current tool result.
    """
    tool_result = state.get("tool_result", {})
    if not tool_result or not tool_result.get("success", False):
        return {
            "chart_config": None,
            "preview_rows": [],
            "metadata": {"row_count": 0, "execution_time": 0}
        }

    data = tool_result.get("data")
    if not isinstance(data, dict):
        data = {}

    columns = data.get("columns", [])
    rows = data.get("rows", [])    
    
    if not rows:
        return {
            "chart_config": None,
            "preview_rows": [],
            "metadata": {
                "row_count": 0,
                "execution_time": data.get("execution_time_ms", 0) / 1000.0 if isinstance(data, dict) else 0,
            }
        }
    # 1. Generate core chart config (Always)
    generator = ChartGenerator()
    chart_config = generator.generate_config(columns, rows)
    
    # Store what the chart type *should* be if they toggle to chart view
    chart_config["chart_type"] = chart_config.get("type", "bar")
    
    plan = state.get("plan", {})
    needs_chart = plan.get("needs_chart", False)
    
    if not needs_chart:
        logger.info("Defaulting to table view as user did not explicitly request a chart.")
        chart_config["type"] = "table"
        
    # Ensure raw data is explicitly available for the table toggle
    if not chart_config.get("data"):
        chart_config["data"] = rows[:100]
    
    # 2. Extract standard fields
    # Return top 20 rows specifically for preview
    preview_rows = rows[:20]
    
    # Combined metadata
    metadata = {
        "row_count": data.get("row_count") or len(rows),
        "execution_time": data.get("execution_time_ms", 0) / 1000.0, # seconds
    }
    
    return {
        "chart_config": chart_config,
        "preview_rows": preview_rows,
        "metadata": metadata
    }
