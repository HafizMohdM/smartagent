"""
Utility to analyze SQL query results and determine the best visualization format.
Supports: bar, line, pie, table, stacked_bar, horizontal_bar, area, combo,
          histogram, scatter, bubble, heatmap, treemap, kpi_card, gauge
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# All supported chart types
CHART_TYPES = {
    "basic":        ["bar", "line", "pie", "table"],
    "advanced":     ["stacked_bar", "horizontal_bar", "area", "combo"],
    "distribution": ["histogram", "box_plot"],
    "relationship": ["scatter", "bubble", "heatmap"],
    "hierarchy":    ["treemap"],
    "kpi":          ["kpi_card", "gauge"],
}
ALL_CHART_TYPES = [t for group in CHART_TYPES.values() for t in group]

# Column name patterns that are useless as chart axes
_SKIP_PATTERNS = re.compile(
    r'\b(id|uuid|guid|hash|token|password|created_by|updated_by|is_|has_)\b',
    re.IGNORECASE,
)

# Metadata fields injected by the pipeline — never use as chart axes
_METADATA_FIELDS = {'_source_db', '_row_num', '_rank', '_id'}

def _is_skip_column(col: str) -> bool:
    return bool(_SKIP_PATTERNS.search(col)) or col.lower().endswith('_id') or col.lower() in _METADATA_FIELDS


def _is_numeric_col(col: str, rows: List[Dict[str, Any]]) -> bool:
    for row in rows[:5]:
        val = row.get(col)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return True
        if isinstance(val, str) and val.replace('.', '', 1).lstrip('-').isdigit():
            return True
        return False
    return False


def enforce_chart_logic(
    x_axis: str,
    y_axis: str,
    sql: str,
    rows: List[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """
    Backend safety net — if Y-axis is non-numeric, wrap SQL in COUNT(*) aggregation.
    Returns (x_axis, corrected_y_axis, corrected_sql).
    """
    if not rows or not x_axis:
        return x_axis, y_axis, sql

    y_is_numeric = y_axis and _is_numeric_col(y_axis, rows)
    if not y_is_numeric:
        logger.warning(
            f"enforce_chart_logic: Y-axis '{y_axis}' is non-numeric. "
            f"Auto-correcting to COUNT(*) grouped by '{x_axis}'."
        )
        corrected_sql = (
            f"SELECT {x_axis}, COUNT(*) AS value "
            f"FROM ({sql.rstrip(';')}) AS _sub "
            f"GROUP BY {x_axis} "
            f"ORDER BY value DESC "
            f"LIMIT 10"
        )
        return x_axis, "value", corrected_sql

    return x_axis, y_axis, sql


class ChartGenerator:
    """
    Analyzes query results and selects the best chart type with correct axes.
    """

    DATE_KEYWORDS = {"date", "time", "year", "month", "day", "created", "updated", "timestamp", "period", "week"}
    AGG_HINTS     = re.compile(r'(count|sum|avg|average|total|amount|revenue|salary|hours|rate|score|percent)', re.I)
    MAX_ROWS      = 50

    def generate_config(self, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not columns or not rows:
            return {"type": "table", "data": []}

        # Normalise rows
        normalized: List[Dict[str, Any]] = []
        for r in rows:
            if isinstance(r, dict):
                normalized.append(r)
            elif isinstance(r, (list, tuple)):
                normalized.append(dict(zip(columns, r)))
            else:
                normalized.append({columns[0]: r})

        chart_data = normalized[:self.MAX_ROWS]
        col_types  = self._detect_column_types(columns, chart_data)

        numeric_cols     = [c for c, t in col_types.items() if t == "numeric"     and not _is_skip_column(c)]
        date_cols        = [c for c, t in col_types.items() if t == "date"        and not _is_skip_column(c)]
        categorical_cols = [c for c, t in col_types.items() if t == "categorical" and not _is_skip_column(c)]

        # Prefer aggregation-named numeric columns
        agg_numeric  = [c for c in numeric_cols if self.AGG_HINTS.search(c)]
        best_numeric = agg_numeric[0] if agg_numeric else (numeric_cols[0] if numeric_cols else None)

        # ── KPI card: single aggregated value ──────────────────────────────
        if len(columns) == 1 and best_numeric:
            val = chart_data[0].get(best_numeric, 0) if chart_data else 0
            return {"type": "kpi_card", "y_axis": best_numeric,
                    "kpi_value": val, "data": chart_data}

        # ── Scatter: exactly 2 numeric columns ─────────────────────────────
        if len(numeric_cols) >= 2 and not date_cols and not categorical_cols:
            return {"type": "scatter", "x_axis": numeric_cols[0], "y_axis": numeric_cols[1],
                    "data": chart_data}

        # ── Heatmap: 2 categorical + 1 numeric ─────────────────────────────
        if len(categorical_cols) >= 2 and best_numeric:
            unique_x = len(set(str(r.get(categorical_cols[0])) for r in chart_data))
            unique_y = len(set(str(r.get(categorical_cols[1])) for r in chart_data))
            if unique_x <= 20 and unique_y <= 20:
                return {"type": "heatmap",
                        "x_axis": categorical_cols[0], "y_axis": categorical_cols[1],
                        "value_col": best_numeric, "data": chart_data}

        # ── Line / Area: time-series ────────────────────────────────────────
        if date_cols and best_numeric:
            chart_type = "area" if self.AGG_HINTS.search(best_numeric) else "line"
            return {"type": chart_type, "x_axis": date_cols[0], "y_axis": best_numeric,
                    "data": chart_data}

        # ── Categorical + numeric ───────────────────────────────────────────
        if categorical_cols and best_numeric:
            unique_cats = len(set(str(r.get(categorical_cols[0])) for r in chart_data))

            # Pie: ≤ 10 categories
            if unique_cats <= 10:
                return {"type": "pie", "x_axis": categorical_cols[0], "y_axis": best_numeric,
                        "data": chart_data[:10]}

            # Stacked bar: second categorical available
            if len(categorical_cols) >= 2:
                return {"type": "stacked_bar",
                        "x_axis": categorical_cols[0], "y_axis": best_numeric,
                        "stack_col": categorical_cols[1], "data": chart_data}

            # Horizontal bar: many categories
            if unique_cats > 15:
                return {"type": "horizontal_bar", "x_axis": categorical_cols[0],
                        "y_axis": best_numeric, "data": chart_data}

            return {"type": "bar", "x_axis": categorical_cols[0], "y_axis": best_numeric,
                    "data": chart_data}

        # ── Histogram: single numeric ───────────────────────────────────────
        if best_numeric and not categorical_cols:
            return {"type": "histogram", "x_axis": best_numeric, "data": chart_data}

        # ── Fallback: table ─────────────────────────────────────────────────
        return {"type": "table", "data": chart_data}

    def _detect_column_types(self, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, str]:
        col_types  = {}
        sample_row = rows[0] if rows else {}

        for col in columns:
            val       = sample_row.get(col)
            col_lower = col.lower()

            if any(kw in col_lower for kw in self.DATE_KEYWORDS):
                col_types[col] = "date"; continue

            if isinstance(val, (datetime, str)) and self._is_date_string(str(val)):
                col_types[col] = "date"; continue

            if isinstance(val, (int, float)):
                col_types[col] = "categorical" if (col_lower.endswith("_id") or col_lower == "id") else "numeric"
                continue

            if isinstance(val, str) and val.replace(".", "", 1).isdigit():
                col_types[col] = "numeric"; continue

            col_types[col] = "categorical"

        return col_types

    def _is_date_string(self, val: str) -> bool:
        if re.match(r"^\d{4}-\d{2}-\d{2}", val):
            return True
        if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", val, re.I):
            return True
        return False


def validate_chart_data(columns: List[str], rows: List[Dict[str, Any]], chart_type: str = "bar") -> Dict[str, Any]:
    """
    Validate and enforce chart-safe data using ChartSafeEnforcer.
    Returns a dict with validated chart config or table fallback.
    
    This is the bridge between the existing chart_generator and the new
    ChartSafeEnforcer. Call this before finalizing chart output.
    """
    from backend.data.executor.chart_enforcer import ChartSafeEnforcer
    
    enforcer = ChartSafeEnforcer()
    result = enforcer.enforce(rows, columns, chart_type)
    
    config = {
        "type": result.chart_type,
        "x_axis": result.x_axis,
        "y_axis": result.y_axis,
        "data": result.data,
        "aggregation_applied": result.aggregation_applied,
    }
    
    if result.explanation:
        config["explanation"] = result.explanation
        config["original_type"] = result.original_type
    
    return config
