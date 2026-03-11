"""
AI Agent Platform — Main Application Entry Point.

Boots up the FastAPI server with:
  - CORS configuration
  - JWT authentication middleware
  - Session manager (Redis-backed with in-memory fallback)
  - Agent orchestrator (LangGraph)
  - Tool registry with DatabaseTool registered
  - All API route modules
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.api.middleware.auth import AuthMiddleware
from backend.api.routes import auth, services, chat, health, connections, queries
from backend.memory.session_manager import SessionManager
from backend.agent.orchestrator import AgentOrchestrator
from backend.tools.registry import ToolRegistry
from backend.services.database.tool import DatabaseTool

# ── Logging ────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ai-agent-platform")


# ── Application lifespan ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("  AI Agent Platform — Starting Up")
    logger.info("=" * 60)

    # 1. Initialise Redis (optional, falls back to in-memory)
    redis_client = None
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        await redis_client.ping()  # type: ignore
        logger.info(f"✓ Redis connected: {settings.REDIS_URL}")
    except Exception as e:
        logger.warning(f"✗ Redis unavailable ({e}). Using in-memory sessions.")
        redis_client = None

    app.state.redis = redis_client

    # 2. Session manager
    session_manager = SessionManager(redis_client=redis_client)
    app.state.session_manager = session_manager
    logger.info("✓ Session manager initialised")

    # 3. Database tool
    db_tool = DatabaseTool(session_manager=session_manager)
    app.state.db_tool = db_tool

    # 4. Tool registry
    registry = ToolRegistry()
    registry.register(db_tool)
    app.state.tool_registry = registry
    logger.info(f"✓ Tool registry: {registry.count} tool(s) registered")

    # 5. Agent orchestrator
    orchestrator = AgentOrchestrator(session_manager=session_manager)
    app.state.orchestrator = orchestrator
    logger.info("✓ Agent orchestrator initialised (LangGraph)")

    # 6. Seed default admin user if none exist
    try:
        from backend.database.session import get_db
        from backend.crud.user import get_user_by_email, create_user
        from backend.security.hashing import hash_password
        from backend.database.engine import async_session_maker

        async with async_session_maker() as db:
            existing = await get_user_by_email(db, "admin@example.com")
            if not existing:
                hashed = hash_password("admin123")
                await create_user(db, email="admin@example.com", password_hash=hashed, name="Admin")
                logger.info("✓ Default admin user created (admin@example.com / admin123)")
            else:
                logger.info("✓ Admin user already exists")
    except Exception as e:
        logger.warning(f"✗ Could not seed admin user: {e}")

    logger.info("=" * 60)
    logger.info("  Platform ready — listening on http://%s:%s", settings.HOST, settings.PORT)
    logger.info("  API docs:  http://%s:%s/docs", settings.HOST, settings.PORT)
    logger.info("=" * 60)

    yield  # ── Application is running ──

    # Shutdown
    logger.info("Shutting down...")
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed.")
    logger.info("Goodbye.")


# ── FastAPI Application ────────────────────────────────────────────

app = FastAPI(
    title="AI Agent Platform",
    description=(
        "A production-grade local AI agent platform with LangGraph orchestration. "
        "Supports multi-step reasoning, tool routing, and extensible service connectors."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

# ── Route Registration ─────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(queries.router)
app.include_router(services.router)
app.include_router(chat.router)
app.include_router(health.router)


# ── CLI Entry Point ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL,
    )
