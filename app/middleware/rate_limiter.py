"""
app/middleware/rate_limiter.py
GAP 3 FIX: Rate limiting via slowapi.
PRD §4.3 (FR-RATE): 10 req/min per user, 100/min per org on POST /repairs.
MVP: per-IP limiting. V2: per-user/per-org using JWT claims.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _get_ip(request: Request) -> str:
    """Key function: rate limit by client IP."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_ip)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": str(exc.retry_after) if hasattr(exc, "retry_after") else "60",
        },
    )
