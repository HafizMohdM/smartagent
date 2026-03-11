"""
SQL Validator — ensures only safe, read-only queries are executed.
Blocks all data-modification and schema-alteration statements.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Statements that are categorically blocked
BLOCKED_KEYWORDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "ALTER",
    "TRUNCATE",
    "INSERT",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "CALL",
    "MERGE",
    "REPLACE",
]

# Patterns that indicate SQL injection or suspicious constructs
SUSPICIOUS_PATTERNS = [
    r";\s*(DROP|DELETE|UPDATE|ALTER|TRUNCATE|INSERT|CREATE)",  # chained destructive
    r"--",          # single-line comment (potential injection)
    r"/\*",         # block comment (potential injection)
    r"xp_",         # SQL Server extended procedures
    r"INFORMATION_SCHEMA\.\w+\s+WHERE.*DROP",  # schema + destructive
]


class SQLValidator:
    """Validates SQL queries to ensure they are safe read-only operations."""

    def __init__(self, blocked_keywords: list | None = None):
        self._blocked = [kw.upper() for kw in (blocked_keywords or BLOCKED_KEYWORDS)]
        import re as re_mod
        self._suspicious_patterns: list[re_mod.Pattern[str]] = [
            re_mod.compile(p, re_mod.IGNORECASE) for p in SUSPICIOUS_PATTERNS
        ]

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate a SQL string for safety.

        Returns:
            (is_valid, reason) — if invalid, reason explains why.
        """
        if not sql or not sql.strip():
            return False, "Empty SQL query."

        normalised = sql.strip().upper()

        # 1. Must start with SELECT or WITH (for CTEs)
        if not (normalised.startswith("SELECT") or normalised.startswith("WITH")):
            return False, (
                f"Only SELECT queries are allowed. "
                f"Query starts with: {normalised.split()[0]}"
            )

        # 2. Check for blocked keywords as standalone tokens
        for keyword in self._blocked:
            # Use word boundary regex to avoid false positives like "UPDATED_AT"
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, normalised):
                return False, (
                    f"Blocked operation detected: {keyword}. "
                    f"Only read-only queries are permitted."
                )

        # 3. Check for multiple statements (semicolons)
        # Allow trailing semicolons but block multiple statements
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        if len(statements) > 1:
            return False, "Multiple SQL statements are not allowed."

        # 4. Check for suspicious injection patterns
        for regex_pattern in self._suspicious_patterns:
            if regex_pattern.search(sql):
                return False, (
                    "Suspicious SQL pattern detected. Query rejected for safety."
                )

        logger.info("SQL validation passed.")
        return True, "Query is valid."
