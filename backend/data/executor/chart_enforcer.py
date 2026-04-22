"""
Chart-Safe Enforcer — strict output validation for chart data.

Guarantees downstream visualization never breaks by enforcing:
  1. X-axis MUST be categorical (string/date) — never numeric ID
  2. Y-axis MUST be numeric — if string, auto-aggregate with COUNT(*)
  3. _source_db and metadata fields EXCLUDED from axes
  4. Data MUST be aggregated for chart types requiring GROUP BY
  5. If valid chart impossible → return explanation, not broken chart
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Fields to always exclude from chart axis selection
EXCLUDED_FIELDS = {"_source_db", "_row_num", "_rank", "_id"}

# Chart types that require aggregated data
AGGREGATION_REQUIRED = {
    "bar", "horizontal_bar", "stacked_bar", "pie",
    "line", "area", "heatmap", "treemap", "combo",
}

# Chart types that work with raw data
RAW_DATA_OK = {"scatter", "histogram", "table", "kpi_card", "gauge"}


@dataclass
class ChartReadyData:
    """Strict chart output contract — guaranteed safe for rendering."""
    x_axis: str
    y_axis: str
    chart_type: str
    data: List[Dict[str, Any]]
    aggregation_applied: bool = False
    explanation: Optional[str] = None     # Set when chart fallback occurs
    original_type: Optional[str] = None   # The intended type before fallback


class ChartSafeEnforcer:
    """
    Ensures chart data meets strict format requirements.

    Call enforce() before sending data to the frontend. If the data
    can't be charted safely, it returns a table fallback with an explanation.
    """

    def enforce(
        self,
        rows: List[Dict[str, Any]],
        columns: List[str],
        chart_type: str,
    ) -> ChartReadyData:
        """
        Validate and enforce chart-safe data rules.

        Args:
            rows:       Query result rows.
            columns:    Column names.
            chart_type: Intended chart type (bar, pie, line, etc.)

        Returns:
            ChartReadyData with guaranteed valid format.
        """
        if not rows or not columns:
            return ChartReadyData(
                x_axis="",
                y_axis="",
                chart_type="table",
                data=[],
                explanation="No data available for chart generation.",
                original_type=chart_type,
            )

        # Filter out excluded fields
        clean_columns = [c for c in columns if c.lower() not in EXCLUDED_FIELDS]
        if not clean_columns:
            clean_columns = columns  # Fallback to original if all excluded

        # Classify columns
        numeric_cols = [c for c in clean_columns if self._is_numeric_column(c, rows)]
        categorical_cols = [c for c in clean_columns if self._is_categorical_column(c, rows)]
        date_cols = [c for c in clean_columns if self._is_date_column(c, rows)]

        # KPI / Gauge: single value, skip complex validation
        if chart_type in ("kpi_card", "gauge"):
            y_col = numeric_cols[0] if numeric_cols else clean_columns[0]
            return ChartReadyData(
                x_axis="",
                y_axis=y_col,
                chart_type=chart_type,
                data=rows[:1],
            )

        # Table: no validation needed
        if chart_type == "table":
            return ChartReadyData(
                x_axis=clean_columns[0] if clean_columns else "",
                y_axis=clean_columns[1] if len(clean_columns) > 1 else "",
                chart_type="table",
                data=rows,
            )

        # ── Select axes ─────────────────────────────────────────────────

        # X-axis: prefer categorical, then date
        x_candidates = categorical_cols + date_cols
        if not x_candidates:
            return self._build_failsafe(
                rows, clean_columns, chart_type,
                "No categorical or date column found for X-axis."
            )
        x_axis = x_candidates[0]

        # Y-axis: must be numeric
        if not numeric_cols:
            # Attempt auto-aggregation: COUNT grouped by X
            logger.warning(
                f"No numeric column for Y-axis. "
                f"Auto-aggregating with COUNT(*) grouped by '{x_axis}'."
            )
            agg_data = self._auto_aggregate(rows, x_axis)
            return ChartReadyData(
                x_axis=x_axis,
                y_axis="value",
                chart_type=chart_type,
                data=agg_data,
                aggregation_applied=True,
            )

        y_axis = numeric_cols[0]

        # ── Validate axes ───────────────────────────────────────────────

        if not self._validate_x_axis(x_axis, rows):
            return self._build_failsafe(
                rows, clean_columns, chart_type,
                f"X-axis column '{x_axis}' contains invalid data types."
            )

        if not self._validate_y_axis(y_axis, rows):
            # Try auto-aggregate
            agg_data = self._auto_aggregate(rows, x_axis)
            return ChartReadyData(
                x_axis=x_axis,
                y_axis="value",
                chart_type=chart_type,
                data=agg_data,
                aggregation_applied=True,
            )

        # ── Check aggregation requirement ───────────────────────────────

        if self._needs_aggregation(chart_type):
            if not self._is_aggregated(rows, x_axis, y_axis):
                logger.info(
                    f"Chart type '{chart_type}' requires aggregation. "
                    f"Auto-aggregating rows."
                )
                agg_data = self._aggregate_by(rows, x_axis, y_axis)
                return ChartReadyData(
                    x_axis=x_axis,
                    y_axis=y_axis,
                    chart_type=chart_type,
                    data=agg_data,
                    aggregation_applied=True,
                )

        # ── Pie chart: cap at 10 slices ─────────────────────────────────

        final_rows = rows
        if chart_type == "pie":
            final_rows = rows[:10]

        return ChartReadyData(
            x_axis=x_axis,
            y_axis=y_axis,
            chart_type=chart_type,
            data=final_rows,
        )

    def _needs_aggregation(self, chart_type: str) -> bool:
        """Check if chart type requires aggregated data."""
        return chart_type in AGGREGATION_REQUIRED

    def _auto_aggregate(
        self, rows: List[Dict[str, Any]], x_col: str
    ) -> List[Dict[str, Any]]:
        """
        Auto-aggregate raw rows into chart-ready format.
        Groups by x_col and counts occurrences.

        Raw: [{name: "A"}, {name: "B"}, {name: "A"}]
        Chart: [{name: "A", value: 2}, {name: "B", value: 1}]
        """
        counter = Counter()
        for row in rows:
            key = str(row.get(x_col, "Unknown"))
            counter[key] += 1

        # Sort by count descending, cap at 20 categories
        sorted_items = counter.most_common(20)
        return [
            {x_col: label, "value": count}
            for label, count in sorted_items
        ]

    def _aggregate_by(
        self,
        rows: List[Dict[str, Any]],
        x_col: str,
        y_col: str,
    ) -> List[Dict[str, Any]]:
        """Aggregate numeric y_col by categorical x_col (SUM)."""
        groups: Dict[str, float] = {}
        for row in rows:
            key = str(row.get(x_col, "Unknown"))
            val = self._to_numeric(row.get(y_col, 0))
            groups[key] = groups.get(key, 0) + val

        # Sort by value descending
        sorted_items = sorted(groups.items(), key=lambda x: x[1], reverse=True)
        return [
            {x_col: label, y_col: value}
            for label, value in sorted_items[:20]
        ]

    def _validate_x_axis(self, col: str, rows: List[Dict[str, Any]]) -> bool:
        """X-axis must contain categorical (string/date) values."""
        for row in rows[:5]:
            val = row.get(col)
            if val is None:
                continue
            if isinstance(val, (str, datetime)):
                return True
            # Numeric values are OK if the column name suggests category
            if isinstance(val, (int, float)):
                col_lower = col.lower()
                if col_lower.endswith("_id") or col_lower == "id":
                    return False  # ID columns are not good X-axes
                return True  # Other numeric columns might be years, etc.
            return True
        return True

    def _validate_y_axis(self, col: str, rows: List[Dict[str, Any]]) -> bool:
        """Y-axis must contain numeric values."""
        for row in rows[:5]:
            val = row.get(col)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                return True
            if isinstance(val, str):
                try:
                    float(val)
                    return True
                except ValueError:
                    return False
        return False

    def _is_numeric_column(self, col: str, rows: List[Dict[str, Any]]) -> bool:
        """Check if a column contains numeric values."""
        col_lower = col.lower()
        # Skip ID columns
        if col_lower.endswith("_id") or col_lower == "id":
            return False
        
        found_numeric = False
        for row in rows[:10]: # Check more rows for better accuracy
            val = row.get(col)
            if val is None or val == "":
                continue
            if isinstance(val, (int, float)):
                found_numeric = True; break
            if isinstance(val, str):
                cleaned = val.replace(",", "").replace("$", "").replace("%", "")
                try:
                    float(cleaned)
                    found_numeric = True; break
                except ValueError:
                    continue # Keep looking
        return found_numeric

    def _is_categorical_column(self, col: str, rows: List[Dict[str, Any]]) -> bool:
        """Check if a column contains categorical (string) values."""
        col_lower = col.lower()
        # Skip known non-categorical patterns
        if col_lower.endswith("_id") or col_lower == "id":
            return False

        found_categorical = False
        for row in rows[:10]:
            val = row.get(col)
            if val is None or val == "":
                continue
            if isinstance(val, str):
                # We allow numeric strings as categorical (e.g. "2021", "Q1")
                # because they are often used as labels on X-axis.
                found_categorical = True; break
            if not isinstance(val, (int, float, datetime)):
                found_categorical = True; break
        
        return found_categorical

    def _is_date_column(self, col: str, rows: List[Dict[str, Any]]) -> bool:
        """Check if a column contains date values."""
        col_lower = col.lower()
        date_keywords = {
            "date", "time", "year", "month", "day", "created",
            "updated", "timestamp", "period", "week",
        }
        if any(kw in col_lower for kw in date_keywords):
            return True
        for row in rows[:3]:
            val = row.get(col)
            if isinstance(val, datetime):
                return True
            if isinstance(val, str) and re.match(r'^\d{4}-\d{2}-\d{2}', val):
                return True
        return False

    def _is_aggregated(
        self, rows: List[Dict[str, Any]], x_col: str, y_col: str
    ) -> bool:
        """Heuristic: check if data appears already aggregated."""
        if len(rows) <= 1:
            return True
        # If all X values are unique → likely aggregated
        x_values = [str(row.get(x_col, "")) for row in rows]
        unique_ratio = len(set(x_values)) / len(x_values) if x_values else 1
        return unique_ratio > 0.8

    def _build_failsafe(
        self,
        rows: List[Dict[str, Any]],
        columns: List[str],
        intended_type: str,
        reason: str,
    ) -> ChartReadyData:
        """Return table view + explanation when chart is impossible."""
        logger.warning(
            f"Chart failsafe triggered for type '{intended_type}': {reason}"
        )
        return ChartReadyData(
            x_axis=columns[0] if columns else "",
            y_axis=columns[1] if len(columns) > 1 else "",
            chart_type="table",
            data=rows,
            explanation=f"Chart cannot be generated: {reason}",
            original_type=intended_type,
        )

    @staticmethod
    def _to_numeric(val: Any) -> float:
        """Safely convert a value to float."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("$", "").replace("%", "")
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0
