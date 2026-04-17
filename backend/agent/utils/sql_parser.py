import re
import logging
from typing import Optional, Set

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

    @staticmethod
    def is_executable(text: str) -> bool:
        """
        Determine if the text is an executable data definition (SQL, METADATA, or LOOKUP).
        Excludes clarifications, errors, and plain summaries.
        """
        if not text:
            return False
        
        upper_text = text.strip().upper()
        
        # 1. Check for valid SQL
        if SQLParser.is_valid_query(text):
            return True
            
        # 2. Check for supported intents
        if upper_text.startswith("TYPE: METADATA") or \
           upper_text.startswith("TYPE: LOOKUP") or \
           upper_text.startswith("TYPE: TABLE_LOOKUP"):
            return True
            
        return False

    @staticmethod
    def extract_tables(sql: str) -> Set[str]:
        """
        Extract table names referenced in FROM and JOIN clauses.
        Handles: schema.table, aliases, multiple tables in FROM.
        Ignores subqueries (parenthesized expressions).
        
        Example:
            SELECT * FROM auth_user u JOIN orders o ON ...
            → {"auth_user", "orders"}
        """
        if not sql:
            return set()

        tables: Set[str] = set()
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', sql.strip())

        # Pattern: FROM table1 [alias] [, table2 [alias]] ...
        # Pattern: [LEFT|RIGHT|INNER|OUTER|CROSS|FULL] JOIN table [alias]
        
        # 1. Extract FROM clause tables
        from_matches = re.finditer(
            r'\bFROM\s+([^()\n;]+?)(?:\s+WHERE\b|\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|\s+UNION\b|\s+INTERSECT\b|\s+EXCEPT\b|\s*;|\s*$)',
            cleaned,
            re.IGNORECASE
        )
        for m in from_matches:
            from_clause = m.group(1).strip()
            # Split by JOIN to avoid capturing join tables in the FROM section
            from_part = re.split(r'\b(?:LEFT|RIGHT|INNER|OUTER|CROSS|FULL)?\s*JOIN\b', from_clause, flags=re.IGNORECASE)[0]
            # Split by comma for multi-table FROM
            for segment in from_part.split(','):
                segment = segment.strip()
                if not segment or segment.startswith('('):
                    continue
                # Take the first token (table name), skip alias
                table_name = segment.split()[0].strip().strip('"').strip('`')
                # Handle schema.table → take just the table part
                if '.' in table_name:
                    table_name = table_name.split('.')[-1]
                if table_name and not table_name.upper().startswith('SELECT'):
                    tables.add(table_name.lower())

        # 2. Extract JOIN clause tables
        join_matches = re.finditer(
            r'\bJOIN\s+(\S+)',
            cleaned,
            re.IGNORECASE
        )
        for m in join_matches:
            table_name = m.group(1).strip().strip('"').strip('`')
            if table_name.startswith('('):
                continue  # Subquery
            if '.' in table_name:
                table_name = table_name.split('.')[-1]
            if table_name and not table_name.upper().startswith('SELECT'):
                tables.add(table_name.lower())

        return tables
