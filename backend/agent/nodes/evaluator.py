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


async def evaluator_node(state: AgentState) -> Dict[str, Any]:
    """Evaluate the tool result and produce a final response or trigger a retry."""
    iteration = state.get("iteration_count", 0) + 1
    tool_result = state.get("tool_result", {})
    plan = state.get("plan", {})
    user_query = state.get("user_query", "")

    # If no tool was needed, produce a conversational response
    if state.get("selected_tool") is None and tool_result.get("data") is None:
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=0.7,
        )
        messages = [
            SystemMessage(content="You are a helpful AI assistant. Respond naturally to the user's message."),
            HumanMessage(content=user_query),
        ]
        response = await llm.ainvoke(messages)
        return {
            "final_response": response.content,
            "is_complete": True,
            "iteration_count": iteration,
        }

    # Force completion if we've hit the retry limit
    if iteration >= MAX_ITERATIONS:
        logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached. Forcing completion.")
        error_msg = tool_result.get("error", "")
        return {
            "final_response": (
                f"I attempted to process your request but encountered difficulties. "
                f"{'Error: ' + error_msg if error_msg else 'The results may be incomplete.'}"
            ),
            "is_complete": True,
            "iteration_count": iteration,
        }

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=0,
    )

    messages = [
        SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"User query: {user_query}\n\n"
            f"Plan: {json.dumps(plan)}\n\n"
            f"Tool result: {json.dumps(tool_result, default=str)}"
        )),
    ]

    response = await llm.ainvoke(messages)

    try:
        content_str = str(response.content)
        evaluation = json.loads(content_str)
    except json.JSONDecodeError:
        evaluation = {
            "is_complete": True,
            "response": response.content,
        }

    is_complete = evaluation.get("is_complete", True)
    final_response = evaluation.get("response", "")

    if not is_complete:
        logger.info(
            f"Evaluator requesting retry (iteration {iteration}): "
            f"{evaluation.get('retry_reason', 'no reason')}"
        )

    return {
        "final_response": final_response,
        "is_complete": is_complete,
        "iteration_count": iteration,
    }
