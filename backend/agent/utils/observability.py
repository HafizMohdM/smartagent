"""
ObservabilityManager — central utility for tracing, token tracking, and cost calculation.
"""

import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ObservabilityManager:
    """Manages spans and telemetry for agent nodes."""
    
    # Cost per 1k tokens (approximate for gpt-4o as of now)
    PRICING = {
        "input": 0.005,
        "output": 0.015
    }

    @staticmethod
    def start_span(node_name: str, state: Dict[str, Any]) -> float:
        """Mark the beginning of a node execution."""
        logger.info(f"Entry: node={node_name} trace_id={state.get('trace_id')}")
        return time.time()

    @staticmethod
    def end_span(node_name: str, start_time: float, state: Dict[str, Any], tokens: Optional[Dict[str, int]] = None):
        """Mark the end of execution and record telemetry."""
        latency = (time.time() - start_time) * 1000 # ms
        
        if "node_telemetry" not in state:
            state["node_telemetry"] = {}
            
        telemetry = {
            "latency_ms": latency,
            "retry_count": state.get("retry_count", 0)
        }
        
        if tokens:
            telemetry["tokens"] = tokens
            # Cost attribution
            cost = (tokens.get("prompt", 0) / 1000 * ObservabilityManager.PRICING["input"]) + \
                   (tokens.get("completion", 0) / 1000 * ObservabilityManager.PRICING["output"])
            telemetry["estimated_cost_usd"] = cost
            
        state["node_telemetry"][node_name] = telemetry
        
        logger.info(f"Exit: node={node_name} latency={latency:.2f}ms cost=${telemetry.get('estimated_cost_usd', 0):.4f}")

    @staticmethod
    def redact_pii(text: str) -> str:
        """Placeholder for PII redaction logic using regex or local models."""
        # TODO: Implement actual redaction
        return text
