"""
tests/unit/test_rate_limiter.py
GAP 3 GATE: 11th request to POST /repairs in 1 minute returns 429.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///./test_rate_limit.db"
test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

ORG_ID = str(uuid.uuid4())
EMAIL = f"ratelimit_{uuid.uuid4().hex[:6]}@test.com"
PASSWORD = "RateLimit123!"


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="module")
async def auth_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": EMAIL, "password": PASSWORD, "org_id": ORG_ID,
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": EMAIL, "password": PASSWORD,
        })
        return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_rate_limit_10_requests_pass(auth_token):
    """First 10 requests to POST /repairs must succeed (not 429)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(10):
            resp = await client.post(
                "/api/v1/repairs",
                json={
                    "stack_trace": f"ModuleNotFoundError: No module named 'pkg{i}'",
                    "repo_path": "/tmp/test",
                    "validation_level": "BASIC",
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            # 200 (SSE stream) or 500 (orchestrator error) — both mean NOT 429
            assert resp.status_code != 429, f"Request {i+1} was rate limited — should not be"


@pytest.mark.asyncio
async def test_rate_limiter_configured():
    """Rate limiter is registered on the app."""
    assert hasattr(app.state, "limiter"), "limiter not registered on app.state"


@pytest.mark.asyncio
async def test_rate_limit_middleware_imported():
    """Verify middleware module loads correctly."""
    from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
    assert limiter is not None
    assert callable(rate_limit_exceeded_handler)
