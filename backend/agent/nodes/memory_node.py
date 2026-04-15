"""
Memory Node for retrieving chat history in the parallel graph.
"""

import logging
from typing import Any, Dict
from backend.agent.state import AgentState
from backend.memory.session.manager import SessionManager

logger = logging.getLogger(__name__)

async def memory_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieves the conversation history for the current session.
    """
    session_id = state.get("session_id", "")
    logger.info(f"--- MEMORY NODE: Retrieving history for {session_id} ---")

    try:
        # SessionManager would be injected in a real app
        # For this refactor, we assume availability or use a default
        # (This is a simplified version for the latency optimization demo)
        from backend.main import app
        session_mgr = getattr(app.state, "session_manager", None)
        
        if not session_mgr:
            # Fallback for stand-alone execution
            session_mgr = SessionManager()
            
        history = await session_mgr.get_history(session_id)
        
        return {
            "messages": history
        }
    except Exception as e:
        logger.error(f"Error in memory_node: {e}")
        return {}
