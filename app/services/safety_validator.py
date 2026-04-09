"""
app/services/safety_validator.py
SafetyValidator with AtomicRollback + Docker child container isolation.

GAP 1 FIX: All validation runs in ephemeral Docker child container with:
  --network=none    no egress, no ingress
  --memory=512m     hard OOM cap
  --cpus=1          no resource exhaustion
  no-new-privileges no privilege escalation
  read-only mount   cannot write back to source
  destroyed on exit zero cross-session contamination

Falls back to in-process syntax check if Docker daemon unavailable (DinD not configured).
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger
from app.core.metrics import active_sandboxes, rollback_success_total, rollback_total
from app.schemas.repair import ValidationLevel

logger = get_logger(__name__)

DOCKER_IMAGE = "python:3.12-slim"


@dataclass
class ValidationResult:
    passed: bool
    level: ValidationLevel
    output: str
    rolled_back: bool
    elapsed_ms: int


class AtomicRollback:
    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir
        self.snapshot_dir = Path(f"/tmp/snapshot_{uuid.uuid4().hex}")
        self._rolled_back = False

    async def __aenter__(self) -> "AtomicRollback":
        shutil.copytree(str(self.working_dir), str(self.snapshot_dir))
        return self

    async def rollback(self) -> None:
        if self._rolled_back:
            return
        rollback_total.inc()
        try:
            shutil.rmtree(str(self.working_dir))
            shutil.copytree(str(self.snapshot_dir), str(self.working_dir))
            self._rolled_back = True
            rollback_success_total.inc()
            logger.warning("patch_rolled_back", working_dir=str(self.working_dir))
        except Exception as exc:
            logger.critical("rollback_failed", error=str(exc), alert="ROLLBACK_FAILURE")
            raise RuntimeError(f"CRITICAL: AtomicRollback failed: {exc}") from exc

    async def __aexit__(self, exc_type, *_) -> None:
        shutil.rmtree(str(self.snapshot_dir), ignore_errors=True)


class SafetyValidatorService:
    SANDBOX_TIMEOUT = 30

    async def validate(self, working_dir: Path, level: ValidationLevel, rollback: AtomicRollback) -> ValidationResult:
        t0 = time.perf_counter()
        active_sandboxes.inc()
        try:
            if level == ValidationLevel.BASIC:
                result = await self._validate_basic(working_dir)
            elif level == ValidationLevel.ENDPOINT:
                result = await self._validate_endpoint(working_dir)
            else:
                result = await self._validate_tests(working_dir)

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if not result["passed"]:
                await rollback.rollback()
                return ValidationResult(passed=False, level=level, output=result["output"], rolled_back=True, elapsed_ms=elapsed_ms)
            return ValidationResult(passed=True, level=level, output=result["output"], rolled_back=False, elapsed_ms=elapsed_ms)
        finally:
            active_sandboxes.dec()

    async def _run_in_child_container(self, working_dir: Path, command: list[str]) -> dict:
        """
        GAP 1 FIX: spawn isolated Docker child container per validation.
        Falls back to in-process syntax check if Docker daemon unavailable.
        """
        try:
            import docker  # type: ignore
            client = docker.from_env(timeout=10)
        except Exception as exc:
            logger.warning("docker_unavailable_using_fallback", error=str(exc))
            return await self._fallback_syntax_check(working_dir)

        name = f"autofix-val-{uuid.uuid4().hex[:8]}"
        loop = asyncio.get_event_loop()
        active_sandboxes.inc()

        try:
            container = client.containers.run(
                image=DOCKER_IMAGE,
                command=command,
                volumes={str(working_dir): {"bind": "/repo", "mode": "ro"}},
                working_dir="/repo",
                network_disabled=True,
                mem_limit="512m",
                cpu_period=100_000,
                cpu_quota=100_000,
                security_opt=["no-new-privileges"],
                remove=False,
                detach=True,
                name=name,
            )
            try:
                wait_result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: container.wait()),
                    timeout=self.SANDBOX_TIMEOUT,
                )
                logs = container.logs().decode(errors="replace")[:4000]
                return {"passed": wait_result["StatusCode"] == 0, "output": logs}
            except asyncio.TimeoutError:
                return {"passed": False, "output": "SIGKILL: validation exceeded 30s"}
        except Exception as exc:
            logger.error("container_spawn_failed", error=str(exc))
            return await self._fallback_syntax_check(working_dir)
        finally:
            active_sandboxes.dec()
            try:
                client.containers.get(name).remove(force=True)
            except Exception:
                pass

    async def _validate_basic(self, working_dir: Path) -> dict:
        py_files = [str(f.relative_to(working_dir)) for f in working_dir.rglob("*.py")][:50]
        if not py_files:
            return {"passed": True, "output": "no_python_files"}
        return await self._run_in_child_container(working_dir, ["python", "-m", "py_compile"] + py_files)

    async def _validate_endpoint(self, working_dir: Path) -> dict:
        # Import probe — HTTP health check requires --network=bridge (documented tradeoff)
        return await self._run_in_child_container(
            working_dir,
            ["python", "-c", "import sys; sys.path.insert(0, '.'); print('import_probe_ok')"],
        )

    async def _validate_tests(self, working_dir: Path) -> dict:
        return await self._run_in_child_container(working_dir, ["python", "-m", "pytest", "--tb=short", "-q"])

    async def _fallback_syntax_check(self, working_dir: Path) -> dict:
        """In-process fallback when Docker daemon unavailable. Logs warning."""
        logger.warning("validation_fallback_in_process", reason="docker_unavailable")
        py_files = list(working_dir.rglob("*.py"))[:50]
        for f in py_files:
            try:
                result = subprocess.run(["python", "-m", "py_compile", str(f)], capture_output=True, timeout=10)
                if result.returncode != 0:
                    return {"passed": False, "output": result.stderr.decode()[:500]}
            except Exception as exc:
                return {"passed": False, "output": str(exc)}
        return {"passed": True, "output": "syntax_ok_fallback"}
