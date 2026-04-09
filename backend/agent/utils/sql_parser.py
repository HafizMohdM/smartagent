import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SQLParser:
    """
    Utility for extracting and validating SQL from AI responses.
    Ensures that only pure SQL (SELECT/WITH) is stored or executed.
    """

    @staticmethod
    def extract_sql(text: str) -> Optional[str]:
        """
        Extract ONLY the SQL part from a mix of natural language and markdown.
        Priority:
        1. Markdown sql blocks (```sql ... ```)
        2. Generic markdown code blocks (``` ... ```)
        3. First occurrence of SELECT or WITH statements
        """
        if not text:
            return None

        # 1. Look for markdown SQL blocks (with or without 'sql' lang tag)
        # Handle ```sql ... ``` and generic ``` ... ```
        sql_block_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if sql_block_match:
            sql = sql_block_match.group(1).strip()
            if SQLParser.is_valid_query(sql):
                return sql

        # 2. Look for keywords if no block found
        # Find first occurrence of SELECT or WITH
        select_match = re.search(r"\b(SELECT|WITH)\b.*", text, re.DOTALL | re.IGNORECASE)
        if select_match:
            sql = select_match.group(0).strip()
            # Clean up if followed by other markdown/text (approximate)
            # Find the end of the SQL statement (semicolon or end of string)
            # We look for the FIRST semicolon as the statement terminator
            end_match = re.search(r"(.*?);", sql, re.DOTALL)
            if end_match:
                sql = end_match.group(1).strip()
            
            if SQLParser.is_valid_query(sql):
                return sql

        return None

    @staticmethod
    def is_valid_query(sql: str) -> bool:
        """
        Ensure the query starts with SELECT or WITH (read-only enforcement).
        """
        if not sql:
            return False
            
        trimmed = sql.strip().upper()
        return trimmed.startswith("SELECT") or trimmed.startswith("WITH")
