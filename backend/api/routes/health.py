"""
Health check route — system status and component health.
"""

from datetime import datetime

from fastapi import APIRouter, Request

from backend.api.models.responses import HealthResponse

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(req: Request):
    """
    System health check.

    Returns the platform status, version, and the health of
    individual components (Redis, registered tools, etc.).
    """
    services = {}

    # Check Redis
    try:
        redis_client = getattr(req.app.state, "redis", None)
        if redis_client:
            await redis_client.ping()
            services["redis"] = "healthy"
        else:
            services["redis"] = "not configured (using in-memory fallback)"
    except Exception:
        services["redis"] = "unhealthy"

    # Check registered tools
    from backend.agent.tools.registry import ToolRegistry
    registry = ToolRegistry()
    services["tools"] = f"{registry.count} registered"

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services=services,
        timestamp=datetime.utcnow().isoformat(),
    )
