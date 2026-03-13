"""
Static SQL Validator for checking queries before execution.
Ensures safety (no data modification) and basic syntax/schema correctness.
"""

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SQLValidator:
    """Performs static analysis on generated SQL queries for safety and optimization."""
    
    # Dangerous keywords that could modify data (Safety Guardrail)
    DANGEROUS_KEYWORDS = [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"
    ]
    
    def __init__(self, schema_context: Optional[str] = None):
        self.schema_context = schema_context

    def validate(self, sql: str) -> Dict[str, Any]:
        """
        Runs multiple validation checks.
        Returns a dictionary with 'is_valid' and 'reason'.
        """
        # 1. Safety Check: No data-modifying commands
        upper_sql = sql.upper()
        for kw in self.DANGEROUS_KEYWORDS:
            if re.search(r'\b' + kw + r'\b', upper_sql):
                return {
                    "is_valid": False,
                    "reason": f"DANGEROUS_OP: Query contains prohibited keyword '{kw}'",
                    "type": "safety"
                }
        
        # 2. Basic Syntax Check (Existence of SELECT)
        if "SELECT" not in upper_sql:
             return {
                "is_valid": False,
                "reason": "SYNTAX: Query does not appear to be a SELECT statement",
                "type": "syntax"
            }

        # 3. Guardrail: Full Table Scan Detection (Simplified)
        # Look for SELECT FROM without WHERE (on tables likely to be large)
        # In a real system, we'd check against table metadata for size.
        if "FROM" in upper_sql and "WHERE" not in upper_sql and "LIMIT" not in upper_sql:
            # We flag it as a warning/low score but allow for small tables in this version
            logger.warning("Query lacks WHERE clause or LIMIT - potential full table scan.")
            # For strict enterprise requirements, we might block this if cost-per-byte is high.
            pass

        return {"is_valid": True, "reason": "Passed static validation", "type": "success"}

    def check_schema_alignment(self, sql: str, schema_info: str) -> Dict[str, Any]:
        """
        (Optional) Check if columns in SQL exist in the provided schema.
        Note: This usually requires a full SQL parser (like sqlglot or pglast).
        """
        # Placeholder for complex schema alignment logic
        return {"is_valid": True}
