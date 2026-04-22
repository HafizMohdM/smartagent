"""
Summarizer Node — generates a concise, natural-language summary of the tool results.
"""

import logging
import json
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import SecretStr

from backend.agent.state import AgentState
from backend.config.settings import settings
from backend.agent.utils.observability import ObservabilityManager

logger = logging.getLogger(__name__)

SUMMARIZER_SYSTEM_PROMPT = """You are an AI data analyst.
Your job is to provide a concise, natural-language summary of a database query result.

STRICT CONSTRAINTS:
1. ONLY return natural language paragraphs. 
2. NEVER include markdown tables, CSV blocks, or code blocks in your response.
3. NEVER include the SQL query itself; it is displayed elsewhere.
4. If the data is empty, explain why (e.g., no matching records).
5. If the user's specific request wasn't found but general data was retrieved (fallback), you MUST inform the user which columns and table were used.

Focus on significant trends, outliers, and answering the user's intent. Be professional but conversational.
"""

# Response Intents
STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
SUMMARY_ALLOWED = "SUMMARY_ALLOWED"

STRUCTURED_KEYWORDS = ["table", "details", "all data", "show records", "list"]

def _to_markdown_table(columns: list, rows: list, limit: int = 10) -> str:
    """Helper to convert results into a clean Markdown table."""
    if not columns or not rows:
        return "No data found"
    
    # 1. Prepare Header
    header = "| " + " | ".join(map(str, columns)) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    # 2. Prepare Rows (First 10)
    visible_rows = rows[:limit]
    formatted_rows = []
    for row in visible_rows:
        vals = []
        for col in columns:
            v = row.get(col)
            # 6. Replace null values with "-"
            if v is None:
                v = "-"
            vals.append(str(v))
        formatted_rows.append("| " + " | ".join(vals) + " |")
    
    table = "\n".join([header, divider] + formatted_rows)
    
    # Check if we exceeded limit
    if len(rows) > limit:
        table += f"\n\n... showing first {limit} rows"
        
    return table

async def summarizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Summarizes the execution result into a natural-language insight,
    or returns structured data strictly if requested.
    """
    start_time = ObservabilityManager.start_span("summarizer", state)
    
    user_query = state.get("user_query", "")
    query_lower = user_query.lower()
    tool_result = state.get("tool_result", {})
    
    # ── Handle Zero Rows ────────────────────────────────────────────
    data = tool_result.get("data", {})
    rows = data.get("rows", []) if isinstance(data, dict) else []
    columns = data.get("columns", []) if isinstance(data, dict) else []
    
    if not tool_result.get("success", False) or not rows:
        msg = "No data found" if not rows and tool_result.get("success") else \
              tool_result.get("error", "An error occurred while fetching data.")
        return {
            "summary": msg,
            "final_response": msg
        }

    # ── Intent Detection ────────────────────────────────────────────
    response_intent = STRUCTURED_OUTPUT if any(kw in query_lower for kw in STRUCTURED_KEYWORDS) else SUMMARY_ALLOWED
    
    # ── 1. Create Lightweight Preview (Top 5 cols, 10 rows) ─────────
    from backend.agent.utils.data_utils import prepare_chat_preview
    preview_data = prepare_chat_preview(data)
    
    preview_cols = preview_data["columns"]
    preview_rows = preview_data["rows"]
    is_truncated = preview_data["meta"].get("is_truncated", False)

    # ALWAYS display preview in a table (Markdown)
    table_str = _to_markdown_table(preview_cols, preview_rows)

    if response_intent == STRUCTURED_OUTPUT:
        final_msg = table_str
        if is_truncated:
            final_msg += f"\n\nShowing 10 of {preview_data['meta']['total_rows']} rows. Save query to view full data."
            
        return {
            "summary": final_msg,
            "final_response": final_msg,
            "is_structured": True,
            "response_intent": response_intent
        }

    # ── Regular Query: Data FIRST, then Summary ──────────────────────
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=0.3,
    )

    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    is_fallback = meta.get("is_fallback", False)
    # Give LLM ONLY the preview snippet
    data_snippet = json.dumps(preview_data, default=str)
    
    fallback_hint = ""
    if is_fallback:
        fallback_hint = (
            f"\n\nNOTE: A specific match wasn't found. Viewing general records from '{meta.get('table_used')}'. "
        )

    messages = [
        SystemMessage(content=(
            f"{SUMMARIZER_SYSTEM_PROMPT}\n\n"
            "STRICT RULES:\n"
            "- Answer based ONLY on provided preview rows.\n"
            "- Do NOT assume full dataset content.\n"
            "- Keep response concise."
        )),
        HumanMessage(content=(
            f"User Query: {user_query}\n\n"
            f"Preview Data: {data_snippet}"
            f"{fallback_hint}"
        ))
    ]

    response = await llm.ainvoke(messages)
    summary_text = str(response.content)

    # ── Explanation MUST come AFTER the table ────────────────────────
    combined_response = f"{table_str}\n\n{summary_text}"
    if is_truncated:
        combined_response += f"\n\nShowing 10 of {preview_data['meta']['total_rows']} rows. Save query to view full data."

    ObservabilityManager.end_span("summarizer", start_time, state)

    return {
        "summary": summary_text,
        "final_response": combined_response,
        "token_usage": state.get("token_usage", 0) + 500
    }
