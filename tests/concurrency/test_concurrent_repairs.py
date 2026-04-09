"""
tests/concurrency/test_concurrent_repairs.py
Concurrency tests: 10 concurrent workers on PR CI, 100 on nightly.
Tests the critical race condition: concurrent confidence updates on the same
memory entry must not lose updates (SELECT FOR UPDATE enforced in repo).
Also tests: cache get/put under concurrent load, fault localizer thread-safety.
"""
from __future__ import annotations

import asyncio
import random
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository
from app.schemas.error_signature import ErrorSignature
from app.services.cache_service import RepairCacheService, CachedFix
from app.services.fault_localizer import FaultLocalizerService
from app.services.memory_service import compute_confidence

CONCURRENCY = int(__import__("os").environ.get("CONCURRENCY_WORKERS", "10"))

TEST_DB_URL = "sqlite+aiosqlite:///./test_concurrency.db"
test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Memory update concurrency ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_memory_updates_no_lost_writes():
    """
    N workers concurrently update success/failure counts on the same memory entry.
    Final count must exactly equal N (no lost writes from race conditions).
    SELECT FOR UPDATE in MemoryRepository prevents the race.
    """
    # Create a single shared memory entry
    async with TestSession() as session:
        async with session.begin():
            entry = MemoryEntry(
                structural_hash=f"test_{uuid.uuid4().hex[:8]}",
                signature_json={"error_type": "KeyError", "module": None, "context": "runtime", "language": "python"},
                error_type="KeyError",
                cached_fix="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+KEY=value\n",
                fix_source="llm",
                validation_level="BASIC",
                confidence=0.70,
            )
            session.add(entry)
        await session.refresh(entry)
        entry_id = entry.id
        initial_success = entry.success_count

    async def update_worker(worker_id: int) -> None:
        async with TestSession() as session:
            async with session.begin():
                repo = MemoryRepository(session)
                # Simulate compute_confidence on current state
                result = await session.get(MemoryEntry, entry_id)
                if result:
                    new_conf = compute_confidence(result)
                    await repo.update_outcome(entry_id, success=True, new_confidence=new_conf)

    # Run N concurrent workers
    workers = [update_worker(i) for i in range(CONCURRENCY)]
    await asyncio.gather(*workers)

    # Verify: success_count must equal exactly CONCURRENCY (no lost writes)
    async with TestSession() as session:
        result = await session.get(MemoryEntry, entry_id)
        assert result is not None
        expected = initial_success + CONCURRENCY
        assert result.success_count == expected, (
            f"Lost writes detected: expected {expected}, got {result.success_count}"
        )


# ── L1 Cache concurrency ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_cache_get_put_no_exceptions():
    """
    N workers concurrently read and write the L1 TTLCache.
    cachetools.TTLCache is NOT thread-safe for asyncio but safe for concurrent coroutines
    on a single event loop. Verify no exceptions under load.
    """
    cache = RepairCacheService()
    errors: list[Exception] = []

    async def cache_worker(i: int) -> None:
        try:
            sig_hash = f"hash_{i % 20}"  # reuse hashes to create contention
            fix = CachedFix(
                structural_hash=sig_hash,
                cached_fix=f"patch_{i}",
                confidence=random.uniform(0.6, 1.0),
                fix_source="llm",
                memory_entry_id=i,
            )
            cache.put(sig_hash, fix)
            result = cache.get(sig_hash)
            if random.random() > 0.8:
                cache.evict(sig_hash)
        except Exception as exc:
            errors.append(exc)

    workers = [cache_worker(i) for i in range(CONCURRENCY)]
    await asyncio.gather(*workers)

    assert not errors, f"Cache raised {len(errors)} exceptions under concurrent load: {errors[:3]}"


# ── FaultLocalizer concurrency ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_fault_localizer_no_state_corruption():
    """
    FaultLocalizerService is stateless — concurrent calls must not corrupt each other.
    Each worker gets its own correct result.
    """
    fl = FaultLocalizerService()
    results: list[ErrorSignature] = []

    traces = [
        ("ModuleNotFoundError: No module named 'sqlalchemy'", "ModuleNotFoundError"),
        ("NameError: name 'pritn' is not defined", "NameError"),
        ("KeyError: 'DATABASE_URL'", "KeyError"),
        ("AttributeError: 'NoneType' object has no attribute 'run'", "AttributeError"),
        ("SyntaxError: invalid syntax", "SyntaxError"),
    ]

    async def localizer_worker(i: int) -> tuple[ErrorSignature, str]:
        trace, expected_type = traces[i % len(traces)]
        sig = fl.parse(trace)
        return sig, expected_type

    worker_results = await asyncio.gather(*[localizer_worker(i) for i in range(CONCURRENCY)])

    for sig, expected_type in worker_results:
        assert sig.error_type == expected_type, (
            f"State corruption: expected {expected_type}, got {sig.error_type}"
        )


# ── Structural hash uniqueness under load ─────────────────────────────────────

@pytest.mark.asyncio
async def test_structural_hash_deterministic_concurrent():
    """
    The same error signature must always produce the same hash,
    even when computed concurrently by N workers.
    """
    sig = ErrorSignature(
        error_type="ModuleNotFoundError",
        module="fastapi",
        context="import_failure",
    )
    expected_hash = sig.structural_hash()

    async def hash_worker(_: int) -> str:
        return sig.structural_hash()

    hashes = await asyncio.gather(*[hash_worker(i) for i in range(CONCURRENCY)])
    unique_hashes = set(hashes)
    assert len(unique_hashes) == 1, f"Hash non-deterministic under concurrency: {unique_hashes}"
    assert unique_hashes.pop() == expected_hash
