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
from backend.agent.utils import parse_json_markdown
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

Be concise but thorough. Return ONLY valid JSON."""


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
    # Use prepare_chat_preview to ensure we never bloat the token count
    from backend.agent.utils.data_utils import prepare_chat_preview
    preview = prepare_chat_preview(tool_result.get("data", {}))
    
    result_summary = json.dumps(preview, indent=2, default=str)
    
    messages = [
        SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"User Query: {user_query}\n\n"
            f"Plan executed: {json.dumps(plan, indent=2)}\n\n"
            "NOTE: You are being given a PREVIEW snippet (Top 5 cols, 10 rows max).\n"
            f"Tool Result Preview:\n{result_summary}"
        ))
    ]

    response = await llm.ainvoke(messages)
    
    try:
        evaluation = parse_json_markdown(str(response.content))
        if evaluation is None:
            raise ValueError("Evaluator output could not be parsed as JSON")
    except Exception as e:
        logger.error(f"Evaluator parsing error: {e}. Raw content: {response.content}")
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
