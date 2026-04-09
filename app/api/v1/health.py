"""app/api/v1/health.py — Health check + Prometheus metrics endpoint."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.services.cache_service import get_repair_cache

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Phase 2 gate: GET /health → 200 with all subsystem statuses."""
    db_ok = False
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    cache = get_repair_cache()

    from app.services.rule_engine import RuleEngineService
    # Rule count from the singleton loaded in repairs router
    try:
        from app.api.v1.repairs import _rule_engine
        rule_count = len(_rule_engine._rules)
    except Exception:
        rule_count = 0

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "cache_hit_rate": cache.hit_rate,
        "rule_count": rule_count,
        "version": "4.0.0",
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    """Prometheus metrics — internal only. Do not expose publicly."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
