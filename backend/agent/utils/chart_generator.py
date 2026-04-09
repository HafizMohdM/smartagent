"""
Utility to analyze SQL query results and determine the best visualization format.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ChartGenerator:
    """
    Analyzes database query results to automatically select and configure 
    a suitable chart type (line, bar, pie) or fallback to table.
    """

    DATE_KEYWORDS = {"date", "time", "year", "month", "day", "created", "updated", "timestamp", "period"}
    MAX_ROWS = 20

    def generate_config(self, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze columns and data to return a structured chart configuration.
        """
        if not columns or not rows:
            return {"type": "table", "data": []}

        # Ensure rows are dictionaries for consistent processing and frontend rendering
        normalized_rows = []
        for r in rows:
            if isinstance(r, dict):
                normalized_rows.append(r)
            elif isinstance(r, (list, tuple)):
                normalized_rows.append(dict(zip(columns, r)))
            else:
                normalized_rows.append({columns[0] if columns else "value": r})

        # Truncate data for visualization
        chart_data = normalized_rows[:self.MAX_ROWS]
        
        # 1. Identify column types
        col_types = self._detect_column_types(columns, chart_data)
        
        # 2. Heuristics for chart selection
        numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
        date_cols = [c for c, t in col_types.items() if t == "date"]
        categorical_cols = [c for c, t in col_types.items() if t == "categorical"]

        # Selection logic
        # A. Line Chart: Best for time-series (Date + Numeric)
        if date_cols and numeric_cols:
            return {
                "type": "line",
                "x_axis": date_cols[0],
                "y_axis": numeric_cols[0],
                "data": chart_data
            }

        # B. Bar/Pie Chart: Categorical + Numeric
        if categorical_cols and numeric_cols:
            unique_cats = len(set(str(r.get(categorical_cols[0])) for r in chart_data))
            
            # Pie Chart: Small number of categories (distribution)
            if unique_cats <= 10:
                return {
                    "type": "pie",
                    "x_axis": categorical_cols[0],
                    "y_axis": numeric_cols[0],
                    "data": chart_data
                }
            
            # Bar Chart: Larger number of categories
            return {
                "type": "bar",
                "x_axis": categorical_cols[0],
                "y_axis": numeric_cols[0],
                "data": chart_data
            }

        # C. Multi-Numeric: Bar Chart fallback (Index + Numeric)
        if numeric_cols:
            return {
                "type": "bar",
                "x_axis": columns[0], # Just use the first column as label
                "y_axis": numeric_cols[0],
                "data": chart_data
            }

        # D. Fallback to Table
        return {
            "type": "table",
            "data": chart_data
        }

    def _detect_column_types(self, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Heuristically detect if a column is numeric, date, or categorical.
        """
        col_types = {}
        sample_row = rows[0] if rows else {}

        for col in columns:
            val = sample_row.get(col)
            col_lower = col.lower()

            # Date detection
            if any(kw in col_lower for kw in self.DATE_KEYWORDS):
                col_types[col] = "date"
                continue
            
            if isinstance(val, (datetime, str)) and self._is_date_string(str(val)):
                col_types[col] = "date"
                continue

            # Numeric detection
            if isinstance(val, (int, float)):
                # If it's ID-like, it might be categorical or just a label
                if col_lower.endswith("_id") or col_lower == "id":
                    col_types[col] = "categorical"
                else:
                    col_types[col] = "numeric"
                continue
            
            if isinstance(val, str) and val.replace(".", "", 1).isdigit():
                col_types[col] = "numeric"
                continue

            # Default: Categorical
            col_types[col] = "categorical"

        return col_types

    def _is_date_string(self, val: str) -> bool:
        """Simple regex check for common date formats."""
        # ISO-like: 2024-01-01
        if re.match(r"^\d{4}-\d{2}-\d{2}", val):
            return True
        # Month name: Jan, February
        if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", val, re.I):
            return True
        return False
