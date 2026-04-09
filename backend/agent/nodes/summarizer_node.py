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
Focus on:
1. Significant trends or patterns.
2. Key outliers or interesting data points.
3. Answering the user's original query directly.

Avoid returning raw JSON or technical jargon unless necessary.
Be professional but conversational.

IMPORTANT: Do NOT include any SQL queries, code blocks, or markdown-formatted SQL in your response. The SQL will be displayed separately in the UI. Focus only on the natural language explanation of the data.
"""

async def summarizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Summarizes the execution result into a natural-language insight.
    """
    start_time = ObservabilityManager.start_span("summarizer", state)
    
    user_query = state.get("user_query", "")
    tool_result = state.get("tool_result", {})
    
    if not tool_result.get("success", False):
        error_msg = tool_result.get("error", "I encountered an error while trying to fetch the data.")
        return {
            "summary": error_msg,
            "final_response": error_msg
        }

    # Handle Successful query with Zero Rows
    data = tool_result.get("data", {})
    rows = data.get("rows", []) if isinstance(data, dict) else []
    if not rows:
        no_data_msg = (
            f"I found the relevant tables in your database, but I couldn't find any specific records matching your question: '{user_query}'. "
            "Please check if the spelling of names matches the database exactly."
        )
        return {
            "summary": no_data_msg,
            "final_response": no_data_msg
        }

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=0.3, # Slightly higher temperature for natural language
    )

    data_summary = json.dumps(tool_result.get("data", {}), default=str)
    # Truncate if too long (just for the LLM)
    if len(data_summary) > 10000:
        data_summary = data_summary[:10000] + "... [TRUNCATED]"

    messages = [
        SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"User Query: {user_query}\n\n"
            f"Query Results: {data_summary}"
        ))
    ]

    response = await llm.ainvoke(messages)
    summary_text = str(response.content)

    # Track tokens (Mocking)
    tokens = {"prompt": 800, "completion": 200}
    ObservabilityManager.end_span("summarizer", start_time, state, tokens=tokens)

    return {
        "summary": summary_text,
        "final_response": summary_text,
        "token_usage": state.get("token_usage", 0) + 1000
    }
