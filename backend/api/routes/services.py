"""
Service management routes — list available services and connect to them.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Request

from backend.api.models.requests import DatabaseConnectionRequest
from backend.api.models.responses import (
    ServiceInfo,
    ServiceListResponse,
    ConnectionResponse,
    StatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/services", tags=["Services"])

# ── Available service definitions ──────────────────────────────────

AVAILABLE_SERVICES: List[ServiceInfo] = [
    ServiceInfo(
        name="PostgreSQL Database",
        type="database",
        description="Connect to a PostgreSQL database and query it using natural language.",
        required_fields=["host", "port", "database", "username", "password"],
    ),
    # Future services can be added here:
    # ServiceInfo(name="Gmail", type="gmail", description="...", required_fields=[...]),
    # ServiceInfo(name="GitHub", type="github", description="...", required_fields=[...]),
]


@router.get("", response_model=ServiceListResponse)
async def list_services():
    """
    List all available services that the agent can connect to.

    Returns a list of services with their required connection fields.
    """
    return ServiceListResponse(services=AVAILABLE_SERVICES)


@router.post("/connect/database", response_model=ConnectionResponse)
async def connect_database(request: DatabaseConnectionRequest, req: Request):
    """
    Connect to a PostgreSQL database for the current session.

    **Example request:**
    ```json
    {
        "host": "localhost",
        "port": 5432,
        "database": "postgres",
        "username": "postgres",
        "password": "root"
    }
    ```
    """
    session_id = getattr(req.state, "session_id", None)
    if not session_id:
        user_id = getattr(req.state, "user_id", "unknown")
        # For SSO users without a session ID in JWT/Header, we can use a stable one based on user_id
        session_id = f"sso_{user_id}"
        logger.info(f"Using fallback SSO session {session_id} for user {user_id}")

    try:
        # Get the database tool from the app state
        db_tool = req.app.state.db_tool
        result = await db_tool.connect(
            session_id=session_id,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
        )
        logger.info(f"Database connected for session {session_id}")
        return ConnectionResponse(
            status="connected",
            service="database",
            details=result,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Connection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("/disconnect/database", response_model=StatusResponse)
async def disconnect_database(req: Request):
    """Disconnect the database for the current session."""
    session_id = getattr(req.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=400, detail="No active session.")

    db_tool = req.app.state.db_tool
    await db_tool.disconnect(session_id)
    return StatusResponse(status="success", message="Database disconnected")
