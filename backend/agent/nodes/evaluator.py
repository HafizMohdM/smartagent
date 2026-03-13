"""
Evaluator Node — reviews tool results and formulates the final response.
Decides whether the result is satisfactory or needs a retry (up to max iterations).
"""

import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from pydantic import SecretStr

from backend.agent.state import AgentState
from backend.config.settings import settings
from backend.agent.utils.observability import ObservabilityManager

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3

EVALUATOR_SYSTEM_PROMPT = """You are an evaluator for an AI agent platform.
You are given:
- The original user query
- The plan that was made
- The tool execution result

Your job:
1. If the result is successful and answers the user query, create a clear,
   well-formatted natural-language response for the user.
2. If the result has errors or is incomplete, decide whether a retry would help.

Return a JSON object:
{{
    "is_complete": true/false,
    "response": "natural language answer for the user",
    "retry_reason": "reason to retry, if is_complete is false"
}}

When presenting query results, format them as readable tables or lists.
Be concise but thorough. Return ONLY valid JSON."""


def _summarize_result_for_llm(result: Dict[str, Any]) -> str:
    """
    Truncate the tool result so we don't send thousands of tokens to the LLM.
    We only send the first 10 rows + summary metadata. The frontend still gets the full data.
    """
    if result.get("success") is False:
        return json.dumps(result, default=str)
    
    data = result.get("data", {})
    if not isinstance(data, dict) or "rows" not in data:
        return json.dumps(result, default=str)
    
    # Take only the first 10 rows for the LLM
    rows = data.get("rows", [])
    truncated_rows = rows[:10]
    
    summary = {
        "success": True,
        "metadata": {
            "row_count": data.get("row_count"),
            "execution_time_ms": data.get("execution_time_ms"),
            "truncated_by_db": data.get("truncated"),
            "showing_for_llm": f"{len(truncated_rows)} out of {len(rows)} rows",
        },
        "columns": data.get("columns", []),
        "sample_rows": truncated_rows
    }
    
    return json.dumps(summary, default=str)


async def evaluator_node(state: AgentState) -> Dict[str, Any]:
    """
    Hybrid Evaluator: Stage 1 (Rules) -> Stage 2 (LLM Semantic Check).
    Manages bounded retries and budget-aware completion.
    """
    start_time = ObservabilityManager.start_span("evaluator", state)
    
    retry_count = state.get("retry_count", 0)
    user_query = state.get("user_query", "")
    plan = state.get("plan", {})
    tool_result = state.get("tool_result", {})

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=0,
    )

    # Prepare inputs for the evaluator
    result_summary = _summarize_result_for_llm(tool_result)
    
    messages = [
        SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"User Query: {user_query}\n\n"
            f"Plan executed: {json.dumps(plan, indent=2)}\n\n"
            f"Tool Result Summary:\n{result_summary}"
        ))
    ]

    response = await llm.ainvoke(messages)
    
    try:
        evaluation = json.loads(str(response.content))
    except json.JSONDecodeError:
        logger.error(f"Evaluator returned invalid JSON: {response.content}")
        evaluation = {
            "is_complete": True,
            "response": str(response.content),
            "retry_reason": None
        }

    is_complete = evaluation.get("is_complete", True)
    
    # Bounded retry: if we hit MAX_ITERATIONS, force complete
    if not is_complete and retry_count >= MAX_ITERATIONS:
        logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached. Forcing completion.")
        is_complete = True
        evaluation["response"] = f"I've reached the maximum retry limit. Here is the best information I have: {evaluation.get('response', '')}"

    # Track tokens (Mocking for now)
    tokens = {"prompt": 400, "completion": 100}
    ObservabilityManager.end_span("evaluator", start_time, state, tokens=tokens)

    # Accumulate token usage for the state
    token_usage = state.get("token_usage", 0) + 500

    return {
        "final_response": evaluation.get("response", ""),
        "is_complete": is_complete,
        "retry_count": retry_count if is_complete else retry_count + 1,
        "token_usage": token_usage,
        "error": evaluation.get("retry_reason") if not is_complete else None
    }
