import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def validate_db_result(result: Any, source: str, trace_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Strictly validates that a database result follows the system-wide contract.
    
    Structure:
    {
        "rows": List[Dict[str, Any]],
        "columns": List[str],
        "meta": Dict[str, Any]
    }
    
    Raises:
    - TypeError: If types are incorrect.
    - KeyError: If required keys are missing.
    """
    ctx = trace_context or {}
    
    try:
        # 1. Base type check
        if not isinstance(result, dict):
            raise TypeError(f"Result from '{source}' must be a dict, got {type(result)}")

        # 2. Key existence check
        required_keys = {"rows", "columns", "meta"}
        missing_keys = required_keys - set(result.keys())
        if missing_keys:
            raise KeyError(f"Result from '{source}' missing required keys: {missing_keys}")

        # 3. Data type validation (MANDATORY)
        if not isinstance(result["rows"], list):
            raise TypeError(f"'{source}' result 'rows' must be a list, got {type(result['rows'])}")
        
        if not all(isinstance(r, dict) for r in result["rows"]):
            raise TypeError(f"'{source}' result 'rows' must be a list of dicts")

        if not isinstance(result["columns"], list):
            raise TypeError(f"'{source}' result 'columns' must be a list, got {type(result['columns'])}")

        if not isinstance(result["meta"], dict):
            raise TypeError(f"'{source}' result 'meta' must be a dict, got {type(result['meta'])}")

        return result

    except (TypeError, KeyError) as e:
        logger.error({
            "event": "contract_violation",
            "source": source,
            "error": str(e),
            "type": str(type(result)),
            "keys": list(result.keys()) if isinstance(result, dict) else None,
            "request_id": ctx.get("request_id"),
            "query_id": ctx.get("query_id"),
            "connection_id": ctx.get("connection_id")
        })
        raise

def get_error_fallback(error: str, source: str = "system", trace_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Provides a safe, schema-consistent fallback response for UI protection."""
    ctx = trace_context or {}
    return {
        "rows": [],
        "columns": [],
        "meta": {
            "row_count": 0,
            "execution_time_ms": 0,
            "error": str(error),
            "source": source,
            "version": "v1",
            "truncated": False,
            "request_id": ctx.get("request_id"),
            "query_id": ctx.get("query_id"),
            "connection_id": ctx.get("connection_id")
        }
    }
