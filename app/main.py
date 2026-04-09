"""
app/main.py
FastAPI application entry point.
Lifespan: DB tables (dev), rule engine warm-up, observability init.
Middleware: correlation_id injection, request logging.
All routers registered under /api/v1.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from alembic import command as alembic_command
from alembic.config import Config
from app.core.config import settings
from app.core.logging import configure_logging, correlation_id_var, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info("autofix_ai_starting", version="4.0.0", env=settings.app_env)

    # GAP 2 FIX: Use Alembic for all environments.
    # Run: alembic upgrade head  (before starting the server)
    # Dev convenience: auto-run migration on startup if not production
    try:
        from alembic.config import Config
        from alembic import command as alembic_command
        alembic_cfg = Config("alembic.ini")
        import asyncio as _asyncio
        loop = _asyncio.get_event_loop()
        loop.run_in_executor(None, lambda: alembic_command.upgrade(alembic_cfg, "head"))
        logger.info("alembic_upgrade_scheduled")
    except Exception as exc:
        logger.warning("alembic_upgrade_failed_falling_back", error=str(exc))
        if not settings.is_production:
            from app.core.database import create_all_tables
            await create_all_tables()
            logger.info("dev_tables_created_fallback")

    # Verify Anthropic API key is set before accepting traffic
    if not settings.anthropic_api_key:
        logger.warning("anthropic_api_key_not_set", detail="LLM layer will fail at runtime")

    # Warm up wiki dir
    from app.services.wiki_service import WikiService
    wiki = WikiService()
    logger.info("wiki_ready", wiki_dir=settings.wiki_dir)

    logger.info("autofix_ai_ready")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    from app.core.database import engine
    await engine.dispose()
    logger.info("autofix_ai_shutdown")


app = FastAPI(
    title="AutoFix AI",
    description="Self-Learning Autonomous Debugging Engine — Production v4.0",
    version="4.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── Rate limiting (GAP 3 FIX) ────────────────────────────────────────────────
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler  # noqa: E402

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend on :3000 and :5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Correlation ID middleware ──────────────────────────────────────────────────
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID", uuid.uuid4().hex)
    correlation_id_var.set(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=elapsed_ms,
    )
    return response


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.v1 import auth, health, memory, repairs, rules, wiki  # noqa: E402

app.include_router(health.router)                          # /health, /metrics
app.include_router(auth.router, prefix="/api/v1")          # /api/v1/auth/*
app.include_router(repairs.router, prefix="/api/v1")       # /api/v1/repairs
app.include_router(rules.router, prefix="/api/v1")         # /api/v1/rules
app.include_router(memory.router, prefix="/api/v1")        # /api/v1/memory
app.include_router(wiki.router, prefix="/api/v1")          # /api/v1/wiki

try:
    alembic_cfg = Config("alembic.ini")
    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("alembic_upgrade_completed")
except Exception as exc:
    logger.warning("alembic_upgrade_failed", error=str(exc))