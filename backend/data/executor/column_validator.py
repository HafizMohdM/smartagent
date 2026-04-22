"""
Column Validator — validates that every column referenced in generated SQL
actually exists in the target schema.

Provides:
  - Column extraction from SELECT, WHERE, GROUP BY, ORDER BY, JOIN ON clauses
  - Schema cross-validation
  - Levenshtein-based fuzzy matching for suggestions
  - Auto-fix capability to correct SQL in place
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Max Levenshtein distance for auto-fix suggestions
MAX_EDIT_DISTANCE = 3

# SQL keywords that should not be treated as column names
SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL",
    "LIKE", "BETWEEN", "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END",
    "AS", "ON", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS",
    "FULL", "GROUP", "BY", "ORDER", "ASC", "DESC", "HAVING", "LIMIT",
    "OFFSET", "UNION", "ALL", "DISTINCT", "COUNT", "SUM", "AVG", "MIN",
    "MAX", "CONCAT", "COALESCE", "CAST", "EXTRACT", "DATE", "TIMESTAMP",
    "TRUE", "FALSE", "WITH", "RECURSIVE", "OVER", "PARTITION", "ROW",
    "ROWS", "RANGE", "UNBOUNDED", "PRECEDING", "FOLLOWING", "CURRENT",
    "FILTER", "WITHIN", "NULLS", "FIRST", "LAST", "ILIKE", "SIMILAR",
    "TO", "ANY", "SOME", "ARRAY", "LATERAL", "FETCH", "NEXT", "ONLY",
    "RETURNING", "INTO", "VALUES", "SET", "DEFAULT", "DO", "NOTHING",
    "CONFLICT", "CONSTRAINT", "CHECK", "REFERENCES", "FOREIGN", "KEY",
    "PRIMARY", "UNIQUE", "INDEX", "USING", "EXCEPT", "INTERSECT",
    "UPDATE", "DELETE", "INSERT", "CREATE", "ALTER", "DROP",
    "TABLE", "COLUMN", "SCHEMA", "DATABASE", "VIEW", "FUNCTION",
    "TRIGGER", "PROCEDURE", "TYPE", "ENUM", "BOOLEAN", "INTEGER",
    "BIGINT", "SMALLINT", "REAL", "FLOAT", "DOUBLE", "PRECISION",
    "NUMERIC", "DECIMAL", "VARCHAR", "CHAR", "TEXT", "BYTEA",
    "INTERVAL", "SERIAL", "BIGSERIAL", "UUID", "JSONB", "JSON",
    "XML", "MONEY", "INET", "CIDR", "MACADDR", "BIT", "VARBIT",
    "POINT", "LINE", "LSEG", "BOX", "PATH", "POLYGON", "CIRCLE",
}


@dataclass
class ValidationResult:
    """Result of column validation."""
    is_valid: bool
    missing_columns: List[str] = field(default_factory=list)
    suggested_fixes: Dict[str, str] = field(default_factory=dict)  # missing → closest
    fixed_sql: Optional[str] = None
    details: str = ""


def _col_name(col: Any) -> str:
    """Extract column name from either a dict or a plain string."""
    if isinstance(col, dict):
        return col.get("name", "")
    return str(col)


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


class ColumnValidator:
    """
    Validates SQL column references against the live schema.

    Workflow:
      1. Extract column references from SQL
      2. Build the set of all valid columns from schema
      3. Report missing columns
      4. Suggest closest matches via Levenshtein distance
      5. Optionally auto-fix the SQL
    """

    def validate(self, sql: str, schema: Dict[str, Any]) -> ValidationResult:
        """
        Validate all column references in SQL against the schema.

        Args:
            sql:    The SQL query to validate.
            schema: The database schema dict {table_name: {columns: [...]}}.

        Returns:
            ValidationResult with missing columns and suggested fixes.
        """
        if not sql or not schema:
            return ValidationResult(
                is_valid=True,
                details="Empty SQL or schema — skipping validation."
            )

        # 1. Extract columns referenced in SQL
        referenced_columns = self._extract_columns_from_sql(sql)

        # 2. Build valid column set from schema
        valid_columns = self._build_valid_columns(schema)

        # 3. Find missing columns
        missing = []
        for col in referenced_columns:
            col_lower = col.lower()
            # Check against valid columns (case-insensitive)
            if col_lower not in valid_columns:
                missing.append(col)

        if not missing:
            return ValidationResult(
                is_valid=True,
                details=f"All {len(referenced_columns)} columns validated OK."
            )

        # 4. Suggest fixes for missing columns
        available_cols = list(valid_columns.keys())
        suggested_fixes = self._suggest_replacements(missing, available_cols)

        # 5. Auto-fix if possible
        fixed_sql = None
        if suggested_fixes:
            fixed_sql = self._auto_fix(sql, suggested_fixes)

        return ValidationResult(
            is_valid=False,
            missing_columns=missing,
            suggested_fixes=suggested_fixes,
            fixed_sql=fixed_sql,
            details=(
                f"Found {len(missing)} invalid column(s): {missing}. "
                f"Suggested fixes: {suggested_fixes}"
            ),
        )

    def _extract_columns_from_sql(self, sql: str) -> Set[str]:
        """
        Parse SELECT, WHERE, GROUP BY, ORDER BY, JOIN ON for column names.

        This is a heuristic parser — not a full SQL parser — but handles
        the vast majority of generated SQL patterns.
        """
        columns: Set[str] = set()

        # Normalize
        cleaned = re.sub(r'\s+', ' ', sql.strip())

        # 1. SELECT clause columns — between SELECT and FROM
        select_match = re.search(
            r'\bSELECT\s+(DISTINCT\s+)?(.*?)\s+FROM\b',
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if select_match:
            select_part = select_match.group(2)
            self._extract_from_clause(select_part, columns)

        # 2. WHERE clause
        where_match = re.search(
            r'\bWHERE\s+(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bHAVING\b|$)',
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if where_match:
            self._extract_identifiers(where_match.group(1), columns)

        # 3. GROUP BY clause
        group_match = re.search(
            r'\bGROUP\s+BY\s+(.*?)(?:\bHAVING\b|\bORDER\b|\bLIMIT\b|$)',
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if group_match:
            self._extract_identifiers(group_match.group(1), columns)

        # 4. ORDER BY clause
        order_match = re.search(
            r'\bORDER\s+BY\s+(.*?)(?:\bLIMIT\b|\bOFFSET\b|$)',
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if order_match:
            self._extract_identifiers(order_match.group(1), columns)

        # 5. JOIN ON clause
        on_matches = re.finditer(
            r'\bON\s+(.*?)(?:\bWHERE\b|\bJOIN\b|\bGROUP\b|\bORDER\b|$)',
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        for m in on_matches:
            self._extract_identifiers(m.group(1), columns)

        return columns

    def _extract_from_clause(self, clause: str, columns: Set[str]) -> None:
        """Extract column names from a SELECT clause (handles aliases, functions)."""
        if clause.strip() == "*":
            return

        # Split by comma (respecting parentheses)
        parts = self._split_respecting_parens(clause)

        for part in parts:
            part = part.strip()
            if not part or part == "*":
                continue

            # Remove alias: "col AS alias" → "col"
            alias_match = re.match(r'(.+?)\s+AS\s+\w+', part, re.IGNORECASE)
            if alias_match:
                part = alias_match.group(1).strip()

            # Handle functions: COUNT(col), SUM(col), etc.
            func_match = re.search(r'\w+\s*\((.*?)\)', part)
            if func_match:
                inner = func_match.group(1).strip()
                if inner and inner != "*":
                    self._extract_identifiers(inner, columns)
                continue

            # Plain column or table.column
            self._extract_identifiers(part, columns)

    def _extract_identifiers(self, text: str, columns: Set[str]) -> None:
        """Extract SQL identifiers (column names) from a text fragment."""
        # Find all word tokens that look like column references
        tokens = re.findall(r'(?:(\w+)\.)?(\w+)', text)
        for _table_prefix, col in tokens:
            upper = col.upper()
            if upper in SQL_KEYWORDS:
                continue
            # Skip numeric literals
            if col.isdigit():
                continue
            # Skip string literals (quoted)
            if col.startswith("'") or col.startswith('"'):
                continue
            columns.add(col)

    def _split_respecting_parens(self, text: str) -> List[str]:
        """Split by comma but respect parenthesized expressions."""
        parts = []
        depth = 0
        current = []
        for ch in text:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts

    def _build_valid_columns(
        self, schema: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Build a lowercase → original-case mapping of all valid columns.
        """
        valid: Dict[str, str] = {}
        for table_name, table_info in schema.items():
            for col in table_info.get("columns", []):
                cn = _col_name(col)
                if cn:
                    valid[cn.lower()] = cn
        return valid

    def _suggest_replacements(
        self,
        missing_cols: List[str],
        available_cols: List[str],
    ) -> Dict[str, str]:
        """
        Find closest valid column for each missing column using Levenshtein distance.

        Returns:
            Dict mapping missing_col → closest_valid_col
            (only includes matches within MAX_EDIT_DISTANCE)
        """
        suggestions: Dict[str, str] = {}

        for missing in missing_cols:
            missing_lower = missing.lower()
            best_match = None
            best_distance = MAX_EDIT_DISTANCE + 1

            for available in available_cols:
                dist = _levenshtein(missing_lower, available)
                if dist < best_distance:
                    best_distance = dist
                    best_match = available

            if best_match and best_distance <= MAX_EDIT_DISTANCE:
                suggestions[missing] = best_match
                logger.info(
                    f"Column fix suggested: '{missing}' → '{best_match}' "
                    f"(edit distance={best_distance})"
                )

        return suggestions

    def auto_fix(self, sql: str, fixes: Dict[str, str]) -> str:
        """
        Replace invalid columns with their closest valid equivalents in SQL.

        Uses word-boundary-aware replacement to avoid partial matches.
        """
        fixed = sql
        for old_col, new_col in fixes.items():
            # Word-boundary replacement (case-insensitive)
            pattern = re.compile(rf'\b{re.escape(old_col)}\b', re.IGNORECASE)
            fixed = pattern.sub(new_col, fixed)
        return fixed

    def _auto_fix(self, sql: str, fixes: Dict[str, str]) -> str:
        """Internal auto-fix used during validation."""
        return self.auto_fix(sql, fixes)
