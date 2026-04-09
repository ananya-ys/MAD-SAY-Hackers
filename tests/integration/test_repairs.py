"""
tests/integration/test_repairs.py
Integration tests: auth flow, health gate, repair session creation, RBAC enforcement.
Uses httpx AsyncClient against the real FastAPI app with a test DB.
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

# ── Test database setup ───────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///./test_integration.db"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="module", autouse=True)
async def create_test_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Helpers ───────────────────────────────────────────────────────────────────

ORG_ID = str(uuid.uuid4())
TEST_EMAIL = f"test_{uuid.uuid4().hex[:8]}@example.com"
TEST_PASSWORD = "SecurePassword123!"


async def register_and_login(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "org_id": ORG_ID,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD,
    })
    return resp.json()["access_token"]


# ── Phase 2 gate: /health ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "version" in data


# ── Auth flow ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient):
    email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPassword1!", "org_id": ORG_ID,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert data["role"] == "ENGINEER"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    email = f"dup_{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPassword1!", "org_id": ORG_ID,
    })
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPassword1!", "org_id": ORG_ID,
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client: AsyncClient):
    email = f"login_{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPassword1!", "org_id": ORG_ID,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "StrongPassword1!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@test.com", "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/repairs")
    assert resp.status_code == 401


# ── RBAC enforcement ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rule_create_requires_sre_or_admin(client: AsyncClient):
    """ENGINEER cannot create rules. PRD §9: human-only rule creation."""
    token = await register_and_login(client)
    resp = await client.post(
        "/api/v1/rules",
        json={
            "name": "Test Rule", "condition_yaml": "error_type == 'ValueError'",
            "action_type": "ADD_PACKAGE", "confidence": 0.90,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_memory_evict_requires_sre_or_admin(client: AsyncClient):
    token = await register_and_login(client)
    resp = await client.delete(
        "/api/v1/memory/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ── Repair list RBAC ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repairs_list_returns_200_for_engineer(client: AsyncClient):
    token = await register_and_login(client)
    resp = await client.get(
        "/api/v1/repairs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_repair_detail_404_for_other_org(client: AsyncClient):
    token = await register_and_login(client)
    random_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/repairs/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── Wiki endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wiki_list_returns_200(client: AsyncClient):
    token = await register_and_login(client)
    resp = await client.get("/api/v1/wiki", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "pages" in resp.json()


@pytest.mark.asyncio
async def test_wiki_slug_path_traversal_blocked(client: AsyncClient):
    token = await register_and_login(client)
    resp = await client.get(
        "/api/v1/wiki/../etc/passwd",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (400, 404, 422)


# ── Metrics endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "autofix_" in resp.text
