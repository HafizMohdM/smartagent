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
from backend.tools.registry import ToolRegistry

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
    registry = ToolRegistry()
    tools_desc = json.dumps(registry.list_tools(), indent=2)

    # Build conversation context
    history_text = ""
    for msg in (state.get("messages") or [])[-10:]:
        history_text += f"{msg['role']}: {msg['content']}\n"

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=0,
        )

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(tools=tools_desc)),
        HumanMessage(content=(
            f"Conversation history:\n{history_text}\n\n"
            f"Current user query: {state['user_query']}"
        )),
    ]

    response = await llm.ainvoke(messages)

    try:
        content_str = str(response.content)
        plan = json.loads(content_str)
    except json.JSONDecodeError:
        logger.error(f"Planner returned invalid JSON: {response.content}")
        plan = {
            "intent": "unknown",
            "tool": "none",
            "parameters": {},
            "reasoning": response.content,
        }

    logger.info(f"Plan: tool={plan.get('tool')}, intent={plan.get('intent')}")
    return {"plan": plan}
