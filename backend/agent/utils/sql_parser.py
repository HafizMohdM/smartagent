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
    def get_response_type(text: str) -> str:
        """Categorize the response based on production tags."""
        if not text:
            return "unknown"
        text_upper = text.upper()
        if "TYPE: SQL" in text_upper:
            return "sql"
        if "TYPE: METADATA" in text_upper:
            return "metadata"
        if "TYPE: LOOKUP" in text_upper:
            return "lookup"
        if "TYPE: ERROR" in text_upper:
            return "error"
        # Fallback to content analysis
        if SQLParser.extract_sql(text):
            return "sql"
        return "text"

    @staticmethod
    def extract_sql(text: str) -> Optional[str]:
        """
        Extract ONLY the SQL part from a mix of natural language and markdown.
        Priority:
        1. QUERY: tag (New strict format)
        2. Markdown sql blocks (```sql ... ```)
        3. Generic markdown code blocks (``` ... ```)
        4. SQL: tag (Legacy/Assistant format)
        5. First occurrence of SELECT or WITH statements
        """
        if not text:
            return None

        # 1. Look for the "QUERY:" tag specifically (Strict Production format)
        query_match = re.search(r"QUERY:\s*(SELECT\b.*?)(?:\n\n|\n[A-Z]+:|$)", text, re.DOTALL | re.IGNORECASE)
        if query_match:
            sql = query_match.group(1).strip()
            if SQLParser.is_valid_query(sql):
                return sql

        # 2. Look for markdown SQL blocks (with or without 'sql' lang tag)
        sql_block_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if sql_block_match:
            sql = sql_block_match.group(1).strip()
            if SQLParser.is_valid_query(sql):
                return sql

        # 3. Look for the "SQL:" tag specifically (Legacy/Assistant format)
        tag_match = re.search(r"SQL:\s*(SELECT\b.*?)(?:\n\n|\n[A-Z]+:|$)", text, re.DOTALL | re.IGNORECASE)
        if tag_match:
            sql = tag_match.group(1).strip()
            if SQLParser.is_valid_query(sql):
                return sql

        # 4. Look for keywords if no block or tag found
        select_match = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
        if select_match:
            start_pos = select_match.start()
            sql_candidate = text[start_pos:].strip()
            
            # Simple heuristic: stop at first semicolon if present
            semicolon_pos = sql_candidate.find(';')
            if semicolon_pos != -1:
                end_pos = semicolon_pos + 1
            else:
                end_pos = len(sql_candidate)
            
            # Additional safety: stop at double newline or next tag
            tag_end_match = re.search(r"\n\n|\n[A-Z]+:", sql_candidate[1:])
            if tag_end_match:
                end_pos = min(end_pos, tag_end_match.start() + 1)

            sql = sql_candidate[:end_pos].strip()
            
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
