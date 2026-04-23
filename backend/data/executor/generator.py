"""
SQL Generator — uses an LLM to convert natural-language queries into SQL.
Takes the database schema and user question, returns a SQL SELECT statement.
"""

import logging
import re
from typing import Set, Optional, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config.settings import settings
from backend.rag.embeddings.service import EmbeddingService
from backend.data.retrieval.hybrid_retriever import HybridTableRetriever

logger = logging.getLogger(__name__)


def remove_limit(sql: str) -> str:
    """Strip any LIMIT clause from a SQL string (used in report mode)."""
    return re.sub(r'\bLIMIT\s+\d+\b', '', sql, flags=re.IGNORECASE).strip()


def validate_chart_sql(sql: str, chart_type: str = "") -> None:
    """
    Raise if the SQL is unsuitable for chart rendering.
    - Charts must aggregate (GROUP BY required).
    - Pie charts must have LIMIT 10 and ORDER BY.
    """
    upper = sql.upper()
    if "GROUP BY" not in upper:
        raise ValueError("Chart SQL requires aggregation — GROUP BY is missing.")
    if chart_type == "pie":
        if "ORDER BY" not in upper:
            raise ValueError("Pie chart SQL must include ORDER BY.")


def enforce_pie_sql(sql: str) -> str:
    """
    Auto-fix pie chart SQL: ensure ORDER BY col DESC LIMIT 10 is present.
    Appends only the missing clauses.
    """
    upper = sql.upper().rstrip("; \n")
    sql = sql.rstrip("; \n")

    if "ORDER BY" not in upper:
        # Order by the second column (the aggregated value) descending
        sql += " ORDER BY 2 DESC"

    if re.search(r'\bLIMIT\s+\d+\b', sql, re.IGNORECASE):
        # Replace existing LIMIT with 10
        sql = re.sub(r'\bLIMIT\s+\d+\b', 'LIMIT 10', sql, flags=re.IGNORECASE)
    else:
        sql += " LIMIT 10"

    return sql


SQL_GENERATION_PROMPT = """You are a production-grade database AI assistant.
{db_context}
{domain_hint}
---

STEP 1: DETECT INTENT

Classify user query into ONE:

1. METADATA_REQUEST  (show tables, list tables, what tables exist)
2. TABLE_LOOKUP      (employees, attendance table)
3. DATA_QUERY        (attendance of Hazel, employee names, salaries)

---

STEP 2: COLUMN MAPPING RULES (CRITICAL — READ CAREFULLY)

⚠️  NEVER invent or shorten column names.
⚠️  ALWAYS use the EXACT column names listed in SCHEMA below.
⚠️  When you alias a table (e.g. AS e), you MUST still use the FULL column name from SCHEMA.

    WRONG:  e.first_name          ← invented, does NOT exist
    WRONG:  e.last_name           ← invented, does NOT exist
    CORRECT: use only what appears in "Columns:" for that table in SCHEMA

{name_column_hints}

SYNONYM RESOLUTION HINTS (Mapped from vague user terms):
{resolved_columns_hint}

NAME SEARCH RULES:
- When searching by a person's name, use the columns listed above.
- For a full name like "Michael Brown", split and match:
    WHERE e.<first_col> = 'Michael' AND e.<last_col> = 'Brown'
  OR use CONCAT:
    WHERE CONCAT(e.<first_col>, ' ', e.<last_col>) = 'Michael Brown'
- If only one name column exists, use LIKE:
    WHERE e.<name_col> LIKE '%Michael Brown%'
- NEVER reference a column not listed in SCHEMA.

GENERAL VAGUE WORD MAPPING:
| User says  | Map to                                          |
|------------|-------------------------------------------------|
| name       | use NAME COLUMNS above                          |
| id         | primary key column of the relevant table        |
| date       | the most relevant date column in SCHEMA         |

If mapping is genuinely ambiguous:
TYPE: CLARIFICATION
MESSAGE: Please specify which column you mean

---

STEP 3: RESPONSE RULES

A. METADATA_REQUEST → Return ONLY:
TYPE: METADATA
DATA:
* table1
* table2

B. TABLE_LOOKUP → Return ONLY:
TYPE: LOOKUP
DATA: <best_matching_table>

C. DATA_QUERY → Return ONLY:
TYPE: SQL
QUERY:
SELECT ...

STRICT RULES (NON-NEGOTIABLE):
1. Use ONLY the provided schema.
2. DO NOT invent tables or columns.
3. DO NOT rename fields.
4. ONLY generate SELECT or WITH queries.
5. ALWAYS include LIMIT 100.
6. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER.
7. Use exact column names from schema.
8. If the query is vague, return a valid general query.
9. DO NOT explain anything.
10. OUTPUT ONLY SQL.

REPORT MODE RULES (apply when query is analytical/aggregated):
* DO NOT add LIMIT unless the user explicitly asks for a limited number of rows
* Prefer GROUP BY + COUNT/SUM/AVG over raw row dumps
* Select only columns relevant to the question — never SELECT *
* If user asks for "full data" or "all records", return complete query without LIMIT

CHART MODE RULES (apply when generating data for visualisation):

AUTO CHART SELECTION (when user does not specify):
  trend / time data      → line or area
  comparison             → bar or horizontal_bar
  distribution           → histogram
  correlation            → scatter
  percentage / share     → pie
  hierarchy / breakdown  → treemap
  single metric          → kpi_card
  2 categories + metric  → heatmap or stacked_bar

CHART-SPECIFIC SQL RULES:
  BAR / HORIZONTAL_BAR:
    SELECT <category>, <AGG()> AS value FROM ... GROUP BY <category> ORDER BY value DESC
  STACKED_BAR:
    SELECT <cat1>, <cat2>, <AGG()> AS value FROM ... GROUP BY <cat1>, <cat2>
  LINE / AREA:
    SELECT <date_col>, <AGG()> AS value FROM ... GROUP BY <date_col> ORDER BY <date_col>
  PIE:
    SELECT <category>, COUNT(*) AS value FROM ... GROUP BY <category> ORDER BY value DESC LIMIT 10
  SCATTER:
    SELECT <numeric_col1>, <numeric_col2> FROM ... (no GROUP BY needed)
  HISTOGRAM:
    SELECT <numeric_col> FROM ... (no GROUP BY — binning done client-side)
  HEATMAP:
    SELECT <cat1>, <cat2>, <AGG()> AS value FROM ... GROUP BY <cat1>, <cat2>
  TREEMAP:
    SELECT <level1>, <level2>, COUNT(*) AS value FROM ... GROUP BY <level1>, <level2>
  KPI_CARD / GAUGE:
    SELECT <AGG()> AS value FROM ... (single row, single column)

AXIS RULES (STRICT):
  X-axis → category or date column ONLY
  Y-axis → numeric aggregation ONLY (COUNT/SUM/AVG)
  If user picks a string column as Y → replace with COUNT(*)
  NEVER use id columns, SELECT *, or ungrouped string fields as Y-axis
  GROUP BY is MANDATORY for all chart types except scatter and histogram

If data is missing:
TYPE: ERROR
MESSAGE: Required data not found in schema

---

STEP 4: FALLBACK
* If keyword match exists → use it
* If semantically weak → still pick the best match
* ONLY error if absolutely nothing matches

---

SCHEMA:
{filtered_schema}

RELATIONSHIPS:
{filtered_relationships}
"""


def normalize_query(query: str) -> str:
    """
    Pre-process vague or name-only inputs into explicit find-by-name queries.

    "Michael Brown"         → "Find employee details where name is 'Michael Brown'"
    "show me Michael Brown" → unchanged (has intent word)
    """
    INTENT_WORDS = {
        "show", "get", "find", "list", "give", "fetch", "display",
        "what", "who", "how", "when", "where", "select", "count",
        "total", "sum", "average", "attendance", "salary", "report",
        "details", "records", "data",
    }
    words = query.strip().split()
    has_intent = any(w.lower() in INTENT_WORDS for w in words)
    if len(words) <= 5 and not has_intent:
        return f"Find employee details where name is '{query.strip()}'"
    return query


def _col_name(col) -> str:
    """Extract column name from either a dict {'name': ...} or a plain string."""
    if isinstance(col, dict):
        return col.get("name", "")
    return str(col)


def _resolve_name_columns(schema: dict) -> str:
    """
    Scan the raw schema (connector output) and return a hint listing the actual
    name-related columns per table. Injected into the prompt so the LLM uses
    real column names instead of guessing short aliases like 'first_name'.
    """
    NAME_PATTERNS = [
        "first_name", "last_name", "firstname", "lastname",
        "given_name", "surname", "full_name", "fullname", "name",
    ]
    hints = []
    for table, info in schema.items():
        cols = [_col_name(c) for c in info.get("columns", [])]
        matched = [c for c in cols if any(p in c.lower() for p in NAME_PATTERNS)]
        if matched:
            hints.append(f"  {table}: {', '.join(matched)}")
    return "\n".join(hints) if hints else "  (no name columns detected in selected tables)"


class SQLGenerator:
    """Generates SQL from natural language using an LLM."""

    def __init__(self):
        from pydantic import SecretStr
        self._llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=0,
        )
        self._embedding_service = EmbeddingService()
        self._hybrid_retriever = HybridTableRetriever(self._embedding_service)

    async def generate(
        self,
        user_query: str,
        schema: dict,
        connection_id: Optional[str] = None,
        error_context: str = None,
        failed_sql: str = None,
        report_mode: bool = False,
        db_name: Optional[str] = None,
        all_db_names: Optional[List[str]] = None,
        domain_hint: str = "",
        resolved_columns_hint: str = "",
    ) -> str:
        """
        Generate a SQL query from a natural-language question.

        Args:
            user_query:    The user's natural-language question.
            schema:        The database schema dict (table → columns).
            error_context: Optional error from a previous failed execution.
            report_mode:   When True, strips LIMIT and favours aggregation.

        Returns:
            A SQL SELECT string (or a TYPE: ... response).
        """
        # 0. Normalize vague / name-only queries
        user_query = normalize_query(user_query)
        logger.info(f"Normalized query: {user_query}")

        # 1. Retrieve relevant tables
        relevant_table_names = await self._hybrid_retriever.aget_relevant_tables(
            user_query, schema, connection_id=connection_id, limit=5
        )

        # Force-include employee table when relevant
        if "employee" in user_query.lower() and "employee_employee" in schema:
            if "employee_employee" not in relevant_table_names:
                relevant_table_names = ["employee_employee"] + relevant_table_names

        if not relevant_table_names:
            logger.info("No tables matched. Providing schema sample to LLM for intent detection.")
            relevant_table_names = list(schema.keys())[:5]

        # 2. Build pruned schema and format for prompt
        pruned_schema = {name: schema[name] for name in relevant_table_names if name in schema}
        formatted_schema, formatted_relationships = await self._format_schema(pruned_schema, connection_id)

        # 3. Resolve actual name columns from the raw schema (not metadata)
        name_column_hints = _resolve_name_columns(pruned_schema)
        logger.info(f"Name column hints: {name_column_hints}")
        logger.info(f"Using tables in prompt: {list(pruned_schema.keys())}")

        db_context = ""
        if db_name:
            if all_db_names and len(all_db_names) > 1:
                indexed_dbs = ", ".join([f"{i+1}. {name}" for i, name in enumerate(all_db_names)])
                db_context = f"\nCURRENT DATABASE CONTEXT: You are generating SQL exclusively for the database named '{db_name}'. The user has selected the following databases in order: {indexed_dbs}. Interpret the user's query and ONLY extract the requirements meant for you. Ignore requests meant for other database indices.\n"
            else:
                db_context = f"\nCURRENT DATABASE CONTEXT: You are generating SQL for the database named '{db_name}'. If the user asks a multi-part question, ONLY answer the part that applies to '{db_name}'. Ignore tables or requirements meant for other databases.\n"

        messages = [
            SystemMessage(content=SQL_GENERATION_PROMPT.format(
                filtered_schema=formatted_schema,
                filtered_relationships=formatted_relationships,
                name_column_hints=name_column_hints,
                db_context=db_context,
                domain_hint=domain_hint,
                resolved_columns_hint=resolved_columns_hint,
            )),
            HumanMessage(content=user_query),
        ]

        if error_context:
            # On retry, also inject the exact column list to prevent the LLM
            # from repeating the same invented column names.
            exact_cols = self._build_exact_column_context(pruned_schema)
            repair_prompt = f"""You are a SQL repair engine.

STRICT RULES:

1. Fix the SQL using ONLY the schema.
2. DO NOT introduce new tables or columns.
3. DO NOT change intent.
4. Replace invalid columns with closest valid column.
5. KEEP LIMIT 100.
6. DO NOT explain.
7. OUTPUT ONLY SQL.

SCHEMA:
{exact_cols}

USER QUERY:
{user_query}

FAILED SQL:
{failed_sql or "Not provided"}

ERROR:
{error_context}

OUTPUT:
Return ONLY corrected SQL."""
            messages.append(SystemMessage(content=repair_prompt))

        response = await self._llm.ainvoke(messages)
        sql = response.content.strip()

        # Strip markdown code fences if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            sql = sql.strip()

        logger.info(f"Generated SQL: {sql[:200]}")

        # In report mode, strip any LIMIT the LLM may have added
        if report_mode:
            sql = remove_limit(sql)
            logger.info("Report mode: LIMIT removed from SQL.")

        return sql

    def _build_exact_column_context(self, schema: dict) -> str:
        """Build a compact table→columns listing from the raw schema for error correction."""
        lines = []
        for table, info in schema.items():
            cols = [_col_name(c) for c in info.get("columns", [])]
            lines.append(f"  {table}: {', '.join(cols)}")
        return "\n".join(lines)

    def _prune_schema(self, user_query: str, schema: dict) -> dict:
        """
        Select only the tables likely to be relevant to the user query.
        Uses keyword matching and foreign key expansion.
        """
        relevant_tables: Set[str] = set()
        query_lower = user_query.lower()
        query_keywords = [w for w in re.findall(r'\w+', query_lower) if len(w) > 2]

        for table_name in schema.keys():
            if any(kw in table_name.lower() for kw in query_keywords):
                relevant_tables.add(table_name)

        for table_name, info in schema.items():
            if table_name in relevant_tables:
                continue
            for col in info.get("columns", []):
                if any(kw in _col_name(col).lower() for kw in query_keywords):
                    relevant_tables.add(table_name)
                    break

        MAX_TABLES = 12
        if len(relevant_tables) < MAX_TABLES:
            expanded_tables = set(relevant_tables)
            for table_name in list(relevant_tables):
                for fk in schema[table_name].get("foreign_keys", []):
                    referred = fk.get("referred_table")
                    if referred in schema:
                        expanded_tables.add(referred)
                for other_table, other_info in schema.items():
                    for other_fk in other_info.get("foreign_keys", []):
                        if other_fk.get("referred_table") == table_name:
                            expanded_tables.add(other_table)
            relevant_tables = expanded_tables if len(expanded_tables) <= MAX_TABLES else set(list(expanded_tables)[:MAX_TABLES])

        if not relevant_tables:
            logger.warning("No relevant tables found. Returning first 15 tables.")
            return {k: v for k, v in list(schema.items())[:15]}

        return {k: v for k, v in schema.items() if k in relevant_tables}

    async def _format_schema(self, schema: dict, connection_id: Optional[str] = None) -> tuple:
        """Format schema dict into a readable string for the LLM prompt."""
        schema_lines = []
        relationship_lines = []
        selected_tables = set(schema.keys())

        for table_name in selected_tables:
            metadata = await self._hybrid_retriever.get_table_metadata(table_name, connection_id)

            description = metadata.get("description", "No description available.")
            col_list = metadata.get("columns", [])
            if not col_list:
                col_list = [_col_name(c) for c in schema[table_name].get("columns", [])]

            # Normalise: col_list may be strings or dicts
            col_names = ", ".join(_col_name(c) for c in col_list)

            schema_lines.append(f"Table: {table_name}")
            schema_lines.append(f"Columns: {col_names}")
            schema_lines.append(f"Description: {description}\n")

            for fk in metadata.get("relationships", []):
                referred_table = fk.get("referred_table")
                if referred_table in selected_tables:
                    relationship_lines.append(
                        f"{table_name}.{fk['column']} → {referred_table}.{fk['referred_column']}"
                    )

        unique_rel = sorted(set(relationship_lines))
        return "\n".join(schema_lines), "\n".join(unique_rel) or "No explicit relationships provided."

    async def generate_fallback(self, user_query: str, schema: dict) -> str:
        """
        Generate a safe fallback query using the LLM when all else fails.
        """
        # Create a simplified schema representation to save tokens
        pruned_schema = {
            t: {"columns": [c.get("name") if isinstance(c, dict) else str(c) for c in info.get("columns", [])]}
            for t, info in schema.items()
        }
        
        prompt = f"""Generate a SAFE fallback SQL.

RULES:
- Use most relevant table
- Use safe columns: id, name, email, status
- NEVER use SELECT *
- LIMIT 50
- No sensitive fields

OUTPUT:
SQL only

SCHEMA:
{pruned_schema}

USER QUERY:
{user_query}"""

        messages = [SystemMessage(content=prompt)]
        response = await self._llm.ainvoke(messages)
        sql = response.content.strip()
        
        # Strip markdown code fences if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
        return sql

    async def extract_query_metadata(self, raw_data: str) -> dict:
        """
        Extract the SQL query and generate a short meaningful title from raw data.
        Ensures rows/columns are ignored as per strict rules.
        """
        prompt = f"""You are a query persistence engine.

STRICT RULES:

1. Extract ONLY:
   - SQL query
   - Short meaningful title
2. DO NOT include:
   - rows
   - columns
   - preview data
3. DO NOT modify SQL.

OUTPUT:

{{
  "title": "...",
  "generated_sql": "..."
}}

RAW DATA:
{raw_data}"""

        messages = [SystemMessage(content=prompt)]
        response = await self._llm.ainvoke(messages)
        content = response.content.strip()
        
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            from backend.agent.utils.sql_parser import SQLParser
            sql = SQLParser.extract_sql(content)
            return {"title": "Saved Query", "generated_sql": sql or ""}

    async def render_full_data(self, data: dict) -> str:
        """
        Render the full dataset using strict rules.
        """
        prompt = f"""You are a data renderer.

You will receive FULL dataset.

STRICT RULES:

1. Show ALL columns.
2. Show ALL rows (within system limits).
3. DO NOT summarize.
4. DO NOT modify values.

FORMAT:

| column1 | column2 | column3 |
|---------|---------|---------|
| value   | value   | value   |

DATASET:
{data}"""

        messages = [SystemMessage(content=prompt)]
        response = await self._llm.ainvoke(messages)
        return response.content.strip()

    async def format_data_preview(self, preview_data: dict) -> str:
        """
        Format data preview strictly into markdown tables.
        """
        prompt = f"""You are a data preview formatter.

You will receive structured data:
{{
  "columns": [...],
  "rows": [...]
}}

STRICT RULES:

1. Show ONLY preview (already limited).
2. DO NOT add or remove columns.
3. DO NOT rename columns.
4. DO NOT show more data.
5. Replace null values with "-".
6. DO NOT output JSON.
7. DO NOT explain full dataset.

FORMAT:

| column1 | column2 | column3 |
|---------|---------|---------|
| value   | value   | value   |

AFTER TABLE:
"Showing preview of data. Save query to view full results."

If empty:
"No data found"

DATA:
{preview_data}"""

        messages = [SystemMessage(content=prompt)]
        response = await self._llm.ainvoke(messages)
        return response.content.strip()
