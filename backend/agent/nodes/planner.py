"""
Planner Node — analyses the user query and produces an action plan.
Uses the LLM to determine intent, select a tool, and extract parameters.
"""

import json
import logging
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from pydantic import SecretStr

from backend.agent.state import AgentState
from backend.config.settings import settings
from backend.agent.tools.registry import ToolRegistry
from backend.agent.utils.observability import ObservabilityManager

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are an intelligent planner for an AI agent platform.
Your job is to analyze the user's query and decide the best course of action.

Available tools:
{tools}

Based on the user query and conversation history, produce a JSON plan with:
{{
    "intent": "brief description of what the user wants",
    "tool": "name of the tool to use (or 'none' if no tool needed)",
    "parameters": {{ ... tool-specific parameters ... }},
    "reasoning": "why you chose this tool and these parameters"
}}

If the user is making casual conversation or asking something that doesn't
require a tool, set tool to "none" and parameters to {{}}.

IMPORTANT: Return ONLY valid JSON. No markdown fences, no extra text."""


async def planner_node(state: AgentState) -> Dict[str, Any]:
    """Analyse user intent and output a structured plan."""
    start_time = ObservabilityManager.start_span("planner", state)
    
    registry = ToolRegistry()
    tools_desc = json.dumps(registry.list_tools(), indent=2)

    retry_count = state.get("retry_count", 0)
    schema_context = state.get("schema_context", "")
    error_context = state.get("error", "")

    # Build conversation context
    history = state.get("messages", [])
    history_text = ""
    for msg in history[-10:]:
        history_text += f"{msg['role']}: {msg['content']}\n"

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=0,
    )

    adaptive_context = ""
    if retry_count > 0:
        adaptive_context = (
            f"\nATTENTION: This is a RETRY attempt (Round {retry_count + 1}).\n"
            f"Previous error/feedback: {error_context}\n"
            "Please analyze the previous failure and adjust your parameters or tool choice accordingly."
        )

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(tools=tools_desc)),
        HumanMessage(content=(
            f"Conversation history:\n{history_text}\n\n"
            f"Database Schema Context (RAG):\n{schema_context}\n\n"
            f"Current user query: {state['user_query']}"
            f"{adaptive_context}"
        )),
    ]

    response = await llm.ainvoke(messages)
    
    # Track tokens (Mocking for now)
    tokens = {"prompt": 800, "completion": 200}
    ObservabilityManager.end_span("planner", start_time, state, tokens=tokens)

    try:
        content_str = str(response.content)
        plan = json.loads(content_str)
    except json.JSONDecodeError:
        logger.error(f"Planner returned invalid JSON: {response.content}")
        plan = {
            "intent": "unknown",
            "tool": "none",
            "parameters": {},
            "reasoning": str(response.content),
        }

    return {
        "plan": plan,
        "token_usage": state.get("token_usage", 0) + 1000
    }
