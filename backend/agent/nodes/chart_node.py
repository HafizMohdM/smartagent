"""
Chart Node — analyzes tools results to generate automatic chart data.
"""

import logging
from typing import Any, Dict

from backend.agent.state import AgentState
from backend.agent.utils.chart_generator import ChartGenerator, enforce_chart_logic
from backend.data.executor.generator import validate_chart_sql, enforce_pie_sql

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

    plan = state.get("plan", {})
    needs_chart = plan.get("needs_chart", False)

    # 1. Generate core chart config
    generator = ChartGenerator()
    chart_config = generator.generate_config(columns, rows)

    # Store the visual chart type separately (used when toggling table ↔ chart)
    chart_config["chart_type"] = chart_config.get("type", "bar")

    if not needs_chart:
        logger.info("Defaulting to table view — user did not explicitly request a chart.")
        chart_config["type"] = "table"

    active_type = chart_config.get("type", "table")

    # 2. Retrieve the generated SQL for validation / correction
    generated_sql = state.get("generated_sql") or (
        tool_result.get("metadata") or {}
    ).get("generated_sql", "")

    # 3. Validate chart SQL (GROUP BY required for non-table charts)
    if active_type != "table" and generated_sql:
        try:
            validate_chart_sql(generated_sql, chart_type=active_type)
        except ValueError as e:
            logger.warning(f"Chart SQL validation failed: {e}. Falling back to table view.")
            chart_config["type"] = "table"
            active_type = "table"

    # 4. enforce_chart_logic — backend safety net
    #    If the Y-axis column is non-numeric, auto-correct to COUNT(*) grouped by X.
    #    We re-execute the corrected SQL against the same connector when possible.
    if active_type != "table":
        x_axis = chart_config.get("x_axis", "")
        y_axis = chart_config.get("y_axis", "")

        corrected_x, corrected_y, corrected_sql = enforce_chart_logic(
            x_axis, y_axis, generated_sql or "", rows
        )

        if corrected_sql != generated_sql and corrected_sql:
            # Re-execute the corrected aggregation query
            session_id = state.get("session_id", "")
            try:
                from backend.agent.tools.registry import ToolRegistry
                registry = ToolRegistry()
                db_tool = registry.get("database_query")
                if db_tool and session_id:
                    connector = db_tool._connectors.get(session_id)
                    if connector and connector.is_connected:
                        from backend.data.executor.executor import SQLExecutor
                        result = await SQLExecutor(connector).execute(corrected_sql)
                        rows = result.get("rows", rows)
                        columns = result.get("columns", columns)
                        logger.info(
                            f"enforce_chart_logic: re-executed corrected SQL, "
                            f"{len(rows)} rows returned."
                        )
            except Exception as exc:
                logger.warning(f"enforce_chart_logic re-execution failed: {exc}. Using original rows.")

            chart_config["x_axis"] = corrected_x
            chart_config["y_axis"] = corrected_y

    # 5. Auto-fix pie: hard cap at 10 slices
    if active_type == "pie":
        rows = rows[:10]

    # 6. Cap data sent to frontend
    MAX_CHART_ROWS = 50
    MAX_TABLE_ROWS = 500

    if active_type == "table":
        chart_config["data"] = rows[:MAX_TABLE_ROWS]
    else:
        chart_config["data"] = rows[:MAX_CHART_ROWS]

    # 7. Preview rows and metadata
    preview_rows = rows[:20]
    metadata = {
        "row_count": data.get("row_count") or len(rows),
        "total_rows": len(rows),
        "execution_time": data.get("execution_time_ms", 0) / 1000.0,
    }

    return {
        "chart_config": chart_config,
        "preview_rows": preview_rows,
        "metadata": metadata,
    }
