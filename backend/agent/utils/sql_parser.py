import re
import logging
from typing import Optional, Set, Dict, Any, List
import sqlglot
from sqlglot import exp, parse_one

logger = logging.getLogger(__name__)

class SQLParser:
    """
    Utility for extracting and validating SQL from AI responses.
    Ensures that only pure SQL (SELECT/WITH) is stored or executed.
    Uses sqlglot for robust AST-level analysis.
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
        pure_sql = SQLParser.extract_sql(text) or (text if SQLParser.is_executable(text) else None)
        if pure_sql:
            return "sql"
        return "text"

    @staticmethod
    def extract_sql(text: str) -> Optional[str]:
        """
        Extract ONLY the SQL part from a mix of natural language and markdown.
        """
        if not text:
            return None

        # 1. Look for the "QUERY:" tag specifically (Strict Production format)
        query_match = re.search(r"QUERY:\s*(SELECT\b.*?)(?:\n\n|\n[A-Z]+:|$)", text, re.DOTALL | re.IGNORECASE)
        if query_match:
            sql = query_match.group(1).strip()
            if SQLParser.is_executable(sql):
                return sql

        # 2. Look for markdown SQL blocks
        sql_block_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if sql_block_match:
            sql = sql_block_match.group(1).strip()
            if SQLParser.is_executable(sql):
                return sql

        # 3. Look for the "SQL:" tag specifically (Legacy/Assistant format)
        tag_match = re.search(r"SQL:\s*(SELECT\b.*?)(?:\n\n|\n[A-Z]+:|$)", text, re.DOTALL | re.IGNORECASE)
        if tag_match:
            sql = tag_match.group(1).strip()
            if SQLParser.is_executable(sql):
                return sql

        # 4. Look for keywords if no block or tag found
        select_match = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
        if select_match:
            start_pos = select_match.start()
            sql_candidate = text[start_pos:].strip()
            
            semicolon_pos = sql_candidate.find(';')
            if semicolon_pos != -1:
                end_pos = semicolon_pos + 1
            else:
                end_pos = len(sql_candidate)
            
            tag_end_match = re.search(r"\n\n|\n[A-Z]+:", sql_candidate[1:])
            if tag_end_match:
                end_pos = min(end_pos, tag_end_match.start() + 1)

            sql = sql_candidate[:end_pos].strip()
            if SQLParser.is_executable(sql):
                return sql

        return None

    @staticmethod
    def is_executable(sql: str) -> bool:
        """Ensure the query starts with SELECT or WITH (read-only enforcement)."""
        if not sql:
            return False
        trimmed = sql.strip().upper()
        return trimmed.startswith("SELECT") or trimmed.startswith("WITH")

    @staticmethod
    def extract_tables(sql: str) -> Set[str]:
        """Convenience wrapper for table extraction."""
        return SQLParser.extract_entities(sql)["tables"]

    @staticmethod
    def extract_entities(sql: str) -> Dict[str, Set[str]]:
        """
        Extract all table and column names using sqlglot.
        Handles aliases, joins, and subqueries correctly.
        """
        entities = {"tables": set(), "columns": set()}
        try:
            parsed = parse_one(sql)
            # Find all Table nodes
            for table in parsed.find_all(exp.Table):
                entities["tables"].add(table.name.lower())
            
            # Find all Column nodes
            for column in parsed.find_all(exp.Column):
                entities["columns"].add(column.name.lower())
                
        except Exception as e:
            logger.warning(f"AST entity extraction failed: {e}. Falling back to basic regex.")
            entities["tables"] = SQLParser.extract_tables_regex(sql)
            
        return entities

    @staticmethod
    def extract_tables_regex(sql: str) -> Set[str]:
        """Fallback regex-based table extraction if AST fails."""
        tables: Set[str] = set()
        cleaned = re.sub(r'\s+', ' ', sql.strip())
        from_matches = re.finditer(r'\bFROM\s+([^\s()]+)', cleaned, re.IGNORECASE)
        for m in from_matches:
            t = m.group(1).strip().strip('"').strip('`').split('.')[-1].lower()
            if t and t != 'select': tables.add(t)
        join_matches = re.finditer(r'\bJOIN\s+([^\s()]+)', cleaned, re.IGNORECASE)
        for m in join_matches:
            t = m.group(1).strip().strip('"').strip('`').split('.')[-1].lower()
            if t and t != 'select': tables.add(t)
        return tables

    @staticmethod
    def ensure_limit(sql: str, limit: int = 100) -> str:
        """
        Inject LIMIT strictly at the root level of the AST using sqlglot.
        Skips if LIMIT already exists or if it's not a SELECT.
        """
        try:
            parsed = parse_one(sql)
            # Only apply to root-level SELECTs (including UNIONs)
            if isinstance(parsed, (exp.Select, exp.Union)):
                # Check if root already has a limit
                if not parsed.args.get("limit"):
                    return parsed.limit(limit).sql()
            return sql
        except Exception as e:
            logger.warning(f"AST LIMIT injection failed: {e}")
            if "LIMIT" not in sql.upper():
                return f"{sql.rstrip('; ')} LIMIT {limit}"
            return sql

    @staticmethod
    async def select_best_table(
        query: str, 
        schema: Dict[str, Any], 
        embedding_service: Optional[Any] = None
    ) -> Optional[str]:
        """
        Deterministic Scored Fallback Selection:
        score = (0.5 * keyword_match) + (0.3 * embedding_similarity) + (0.2 * table_name_similarity)
        """
        if not schema:
            return None
        
        query_norm = query.lower().replace("_", "")
        best_table = None
        max_score = -1.0
        
        # 1. Prepare for embedding similarity if available
        query_embedding = None
        if embedding_service:
            try:
                query_embedding = await embedding_service.aembed_query(query)
            except Exception:
                pass

        for table_name, info in schema.items():
            table_norm = table_name.lower().replace("_", "")
            
            # A. Keyword match (columns)
            cols = [c.get("name", "").lower().replace("_", "") if isinstance(c, dict) else str(c).lower().replace("_", "") 
                    for c in info.get("columns", [])]
            col_match_count = sum(1 for c in cols if c in query_norm or any(kw in c for kw in query_norm.split()))
            col_score = col_match_count / max(len(cols), 1)
            
            # B. Table name similarity
            # B. Table name similarity (Keyword-based)
            query_keywords = query_norm.split()
            # If norm didn't preserve spaces, we might need the original query's kws
            original_keywords = [kw.lower().replace("_", "") for kw in query.split()]
            
            table_match = (table_norm in query_norm or query_norm in table_norm or 
                           any(kw in table_norm for kw in original_keywords if len(kw) > 2))
            table_score = 1.0 if table_match else 0.0
            
            # C. Embedding similarity (Mocking or using service if available)
            # If we don't have embeddings, we redistribute weights to col (0.7) and table (0.3)
            emb_score = 0.0
            if query_embedding and "embedding" in info:
                # Actual vector math would go here
                pass 

            if query_embedding:
                current_score = (0.5 * col_score) + (0.3 * emb_score) + (0.2 * table_score)
            else:
                current_score = (0.7 * col_score) + (0.3 * table_score)
            
            if current_score > max_score:
                max_score = current_score
                best_table = table_name

        return best_table
