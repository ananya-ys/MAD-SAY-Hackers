"""
tests/unit/test_safety_validator.py
GAP 1 GATE: validation runs in Docker child container, not app process.
Tests AtomicRollback, fallback behavior, and container isolation path.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.repair import ValidationLevel
from app.services.safety_validator import AtomicRollback, SafetyValidatorService


@pytest.fixture
def tmp_repo():
    d = Path(tempfile.mkdtemp())
    (d / "main.py").write_text("x = 1\n")
    (d / "requirements.txt").write_text("fastapi\n")
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


@pytest.fixture
def broken_repo():
    d = Path(tempfile.mkdtemp())
    (d / "bad.py").write_text("def foo(:\n")  # syntax error
    yield d
    shutil.rmtree(str(d), ignore_errors=True)


# ── AtomicRollback tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_atomic_rollback_creates_snapshot(tmp_repo):
    rollback = AtomicRollback(tmp_repo)
    async with rollback:
        assert rollback.snapshot_dir.exists()
        assert (rollback.snapshot_dir / "main.py").exists()


@pytest.mark.asyncio
async def test_atomic_rollback_restores_on_rollback(tmp_repo):
    rollback = AtomicRollback(tmp_repo)
    async with rollback:
        # Corrupt working dir
        (tmp_repo / "main.py").write_text("CORRUPTED\n")
        assert (tmp_repo / "main.py").read_text() == "CORRUPTED\n"

        await rollback.rollback()

        # Restored
        assert (tmp_repo / "main.py").read_text() == "x = 1\n"


@pytest.mark.asyncio
async def test_atomic_rollback_idempotent(tmp_repo):
    rollback = AtomicRollback(tmp_repo)
    async with rollback:
        await rollback.rollback()
        await rollback.rollback()  # second call must not raise


@pytest.mark.asyncio
async def test_atomic_rollback_cleans_snapshot(tmp_repo):
    rollback = AtomicRollback(tmp_repo)
    snapshot_path = None
    async with rollback:
        snapshot_path = rollback.snapshot_dir
        assert snapshot_path.exists()
    # After __aexit__, snapshot must be cleaned
    assert not snapshot_path.exists()


# ── SafetyValidatorService — Docker path ─────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_basic_calls_docker_container(tmp_repo):
    """GAP 1 GATE: _validate_basic must attempt Docker, not subprocess."""
    svc = SafetyValidatorService()

    docker_called = []

    async def mock_run_in_child_container(working_dir, command):
        docker_called.append(command)
        return {"passed": True, "output": "mocked_docker_ok"}

    svc._run_in_child_container = mock_run_in_child_container

    result = await svc._validate_basic(tmp_repo)

    assert result["passed"] is True
    assert len(docker_called) == 1
    assert "py_compile" in docker_called[0]


@pytest.mark.asyncio
async def test_validate_tests_calls_docker_container(tmp_repo):
    svc = SafetyValidatorService()
    docker_called = []

    async def mock_run_in_child_container(working_dir, command):
        docker_called.append(command)
        return {"passed": True, "output": "pytest_ok"}

    svc._run_in_child_container = mock_run_in_child_container
    result = await svc._validate_tests(tmp_repo)
    assert "pytest" in docker_called[0]


@pytest.mark.asyncio
async def test_fallback_when_docker_unavailable(tmp_repo):
    """When Docker daemon unavailable, falls back to in-process syntax check."""
    svc = SafetyValidatorService()

    with patch("docker.from_env", side_effect=Exception("Docker not available")):
        result = await svc._run_in_child_container(tmp_repo, ["python", "-m", "py_compile", "main.py"])

    assert isinstance(result, dict)
    assert "passed" in result
    assert "output" in result


@pytest.mark.asyncio
async def test_fallback_syntax_check_passes_valid_file(tmp_repo):
    svc = SafetyValidatorService()
    result = await svc._fallback_syntax_check(tmp_repo)
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_fallback_syntax_check_fails_broken_file(broken_repo):
    svc = SafetyValidatorService()
    result = await svc._fallback_syntax_check(broken_repo)
    assert result["passed"] is False


# ── Full validate() flow ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_passes_and_no_rollback(tmp_repo):
    svc = SafetyValidatorService()
    rollback = AtomicRollback(tmp_repo)

    svc._validate_basic = AsyncMock(return_value={"passed": True, "output": "ok"})

    async with rollback:
        result = await svc.validate(tmp_repo, ValidationLevel.BASIC, rollback)

    assert result.passed is True
    assert result.rolled_back is False


@pytest.mark.asyncio
async def test_validate_fails_and_triggers_rollback(tmp_repo):
    svc = SafetyValidatorService()
    rollback = AtomicRollback(tmp_repo)

    svc._validate_basic = AsyncMock(return_value={"passed": False, "output": "syntax error"})

    # Corrupt to verify rollback restores
    async with rollback:
        (tmp_repo / "main.py").write_text("CORRUPTED\n")
        result = await svc.validate(tmp_repo, ValidationLevel.BASIC, rollback)

    assert result.passed is False
    assert result.rolled_back is True
    assert (tmp_repo / "main.py").read_text() == "x = 1\n"
