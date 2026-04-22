"""
Data Utils — utilities for truncating and compacting data for safe LLM transit.
Ensures large datasets don't hit model token limits.
"""

import re
from typing import List, Dict, Any

def prepare_chat_preview(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Slices raw SQL results down to Top 5 columns and First 10 rows.
    Returns a lightweight preview suitable for Chat and LLM prompts.
    """
    if not result:
        return {}

    raw_columns = result.get("columns", [])
    raw_rows = result.get("rows", [])
    
    # 1. Slice Columns to first 5
    preview_columns = raw_columns[:5]
    
    # 2. Map Rows to those 5 columns and slice to first 10
    preview_rows = []
    for row in raw_rows[:10]:
        preview_rows.append({
            k: row.get(k) for k in preview_columns
        })

    return {
        "columns": preview_columns,
        "rows": preview_rows,
        "meta": {
            **result.get("metadata", {}),
            "preview": True,
            "total_rows": len(raw_rows),
            "total_columns": len(raw_columns),
            "is_truncated": len(raw_rows) > 10 or len(raw_columns) > 5
        }
    }

def compact_history_for_llm(messages: List[Dict[str, str]]) -> str:
    """
    Converts conversation history into a string while stripping heavy 
    Markdown tables to prevent context bloat.
    """
    compacted = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        # Detect and strip Markdown tables
        # Look for headers | col | and dividers | --- |
        if "|" in content and "---" in content:
            # Simple heuristic: replace the table block with a placeholder
            # We keep any preceding or trailing text (like the summary)
            lines = content.split("\n")
            cleaned_lines = []
            is_in_table = False
            table_found_in_msg = False
            
            for line in lines:
                if "|" in line and ("---" in line or (cleaned_lines and "|" in cleaned_lines[-1])):
                    if not is_in_table:
                        cleaned_lines.append("[Data Table Omitted from Context]")
                        is_in_table = True
                        table_found_in_msg = True
                    continue
                else:
                    is_in_table = False
                    cleaned_lines.append(line)
            
            content = "\n".join(cleaned_lines)

        # Truncate extremely long single messages
        if len(content) > 3000:
            content = content[:3000] + "... [Truncated]"

        compacted += f"{role.upper()}: {content}\n"
    
    return compacted
