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

import os
import sys

# Add project root to sys.path to support imports from 'backend' package
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.api.middleware.auth import AuthMiddleware
from backend.api.routes import auth, services, chat, health, connections, queries, reports, dashboards, admin
from backend.memory.session.manager import SessionManager
from backend.agent.orchestrator import AgentOrchestrator
from backend.agent.tools.registry import ToolRegistry
from backend.agent.tools.database_tool import DatabaseTool

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

    # 6. Seed hardcoded users (admin & user) on every startup
    try:
        from backend.data.pool.session import get_db
        from backend.security.user import get_user_by_email, create_user
        from backend.security.hashing import hash_password
        from backend.data.pool.engine import async_session_maker
        from backend.models.tenant import Tenant
        from sqlalchemy.future import select

        async with async_session_maker() as db:
            # Ensure a default tenant exists
            result = await db.execute(select(Tenant).limit(1))
            tenant = result.scalars().first()
            if not tenant:
                tenant = Tenant(name="Default")
                db.add(tenant)
                await db.commit()
                await db.refresh(tenant)
                logger.info(f"✓ Default tenant created: {tenant.id}")

            tenant_id = str(tenant.id)

            # Seed admin@example.com (legacy, keep for migration compat)
            existing_legacy = await get_user_by_email(db, "admin@example.com")
            if not existing_legacy:
                hashed = hash_password("admin123")
                await create_user(
                    db, email="admin@example.com", password_hash=hashed,
                    name="Admin (legacy)", tenant_id=tenant_id, role="admin",
                )
                logger.info("✓ Legacy admin seeded (admin@example.com / admin123)")
            else:
                logger.info("✓ Legacy admin already exists")

            from backend.security.hashing import verify_password

            # Seed admin@admin.local — always approved + active
            existing_admin = await get_user_by_email(db, "admin@admin.local")
            admin_pwd = "admin123"
            if not existing_admin:
                hashed_admin = hash_password(admin_pwd)
                await create_user(
                    db, email="admin@admin.local", password_hash=hashed_admin,
                    name="Admin", tenant_id=tenant_id, role="admin",
                    status="approved", is_active=True,
                )
                logger.info("✓ Admin user seeded (admin@admin.local / admin123)")
            else:
                # Ensure admin is always approved/active regardless of DB state
                if existing_admin.status != "approved" or not existing_admin.is_active or existing_admin.role != "admin":
                    existing_admin.status = "approved"
                    existing_admin.is_active = True
                    existing_admin.role = "admin"
                    await db.commit()
                    logger.info("✓ Admin user status synchronised")
                else:
                    logger.info("✓ Admin user already exists and is up-to-date")

            # NOTE: user@user.local and manager@manager.local are no longer auto-seeded.
            # Users must register via /api/auth/register and be approved by admin.

            # Auto-approve any existing connections that have no status set
            from backend.models.db_connection import DBConnection, ConnectionStatus
            from sqlalchemy import update as sa_update
            await db.execute(
                sa_update(DBConnection)
                .where(DBConnection.status == None)  # noqa: E711
                .values(status=ConnectionStatus.APPROVED, is_admin_owned=True)
            )
            await db.commit()

    except Exception as e:
        logger.warning(f"✗ Could not seed users: {e}")


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
        "Production-grade AI analytics platform with RBAC, approval workflows, "
        "and natural-language database querying.\n\n"
        "## Authentication\n"
        "- **Admin** can login directly.\n"
        "- **User / Manager** must register and be approved by an admin before login.\n\n"
        "## Roles\n"
        "| Role | Permissions |\n"
        "|------|-------------|\n"
        "| `admin` | Full access, approve/reject users & connections |\n"
        "| `manager` | Create connections (pending), edit own connections |\n"
        "| `user` | View approved connections, create connections (pending) |\n"
    ),
    version="2.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
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
app.include_router(reports.router)
app.include_router(dashboards.router)
app.include_router(admin.router)
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
