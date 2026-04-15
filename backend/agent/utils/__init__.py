"""
Utility functions for the AI agent orchestration.
Includes result formatting and truncation logic to manage LLM context windows.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def parse_json_markdown(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse JSON from markdown code blocks.
    If no code block is found, tries to parse the whole text.
    """
    # Try to find JSON in a code block
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text)
    if match:
        content = match.group(1)
    else:
        content = text

    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        # Final fallback: try to find anything that looks like a JSON object
        brace_match = re.search(r"({[\s\S]*})", content)
        if brace_match:
            try:
                return json.loads(brace_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        return None


def truncate_tool_result(result: Dict[str, Any], max_chars: int = 5000) -> str:
    """
    Intelligently truncate a tool result for the LLM evaluator.
    If the result is too large, it summarizes rather than just cutting text.
    """
    if not result:
        return "{}"

    # Extract key components
    success = result.get("success", False)
    data = result.get("data")
    error = result.get("error")
    metadata = result.get("metadata", {})

    # If it's a failure, the error is the most important part
    if not success:
        return json.dumps({
            "success": False,
            "error": error,
            "metadata": metadata
        }, indent=2)

    # If data is small enough, return everything
    full_json = json.dumps(result, default=str, indent=2)
    if len(full_json) <= max_chars:
        return full_json

    # Otherwise, summarize the data part
    summary = {
        "success": True,
        "metadata": metadata,
        "note": f"The full result was too large ({len(full_json)} chars) and has been summarized below."
    }

    if isinstance(data, dict):
        if "rows" in data and "columns" in data:
            # Special handling for database results
            row_count = data.get("row_count", len(data.get("rows", [])))
            columns = data.get("columns", [])
            summary["data_summary"] = {
                "type": "database_result",
                "total_rows": row_count,
                "columns": columns,
                "sample_rows": data.get("rows", [])[:5],  # Keep first 5 rows
                "message": f"Showing 5 of {row_count} rows. All {len(columns)} columns are listed."
            }
        else:
            # General dict summary
            summary["data_summary"] = {
                "keys": list(data.keys()),
                "message": "Data is a large object. Here are the top-level keys."
            }
    elif isinstance(data, list):
        summary["data_summary"] = {
            "total_items": len(data),
            "sample_items": data[:5],
            "message": f"Showing 5 of {len(data)} items."
        }
    else:
        # Fallback truncation
        str_data = str(data)
        summary["data_summary"] = str_data[:max_chars // 2] + "... [TRUNCATED]"

    return json.dumps(summary, indent=2)

async def safe_llm_call(llm: Any, messages: list) -> Any:
    """
    Wrap an LLM call to handle rate limits and other common API errors gracefully.
    Returns the response or raises a custom exception.
    """
    import openai
    try:
        return await llm.ainvoke(messages)
    except openai.RateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        # Check if it's a token limit vs request limit
        if "tokens" in str(e).lower():
            raise ValueError("TOKEN_LIMIT_EXCEEDED")
        raise ValueError("RATE_LIMIT_EXCEEDED")
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise ValueError("LLM_API_ERROR")
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise e
