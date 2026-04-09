<<<<<<< HEAD
from __future__ import annotations
=======
"""
app/services/repair_orchestrator.py
RepairOrchestrator: the central service that runs the full 4-layer repair loop.

Layer stack (strict order — cheaper before expensive):
  1. Rule Engine   < 5ms   $0.000
  2. L1 TTLCache   < 1ms   $0.000
  3. Second Brain  < 50ms  $0.000
  4. LLM Agent     < 30s   $0.003–$0.05

Attempt-aware: failed strategies injected into LLM prompt on retry.
Patch hash guard: same patch twice → LOOP_DETECTED immediately.
All layer updates on every outcome (win or loss).
Audit log written BEFORE first sandbox run (MEOS critical pattern #1).
"""
from __future__ import annotations

import asyncio
>>>>>>> origin/main
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any
<<<<<<< HEAD
from sqlalchemy.ext.asyncio import AsyncSession
=======

from sqlalchemy.ext.asyncio import AsyncSession

>>>>>>> origin/main
from app.core.logging import get_logger, set_repair_session_id
from app.core.metrics import repair_duration_seconds, repair_sessions_total
from app.models.repair_session import RepairStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.repair_repository import RepairRepository
from app.repositories.rule_repository import RuleRepository
from app.schemas.error_signature import ErrorSignature
from app.schemas.repair import (
<<<<<<< HEAD
    ExplainabilityPayload, RepairStatus as SchemaStatus,
    SourceLayer, TraceStep, ValidationLevel,
=======
    AttemptRecord,
    ExplainabilityPayload,
    RepairStatus as SchemaStatus,
    SourceLayer,
    TraceStep,
    ValidationLevel,
>>>>>>> origin/main
)
from app.services.cache_service import CachedFix, get_repair_cache
from app.services.fault_localizer import FaultLocalizerService
from app.services.memory_service import MemoryService
from app.services.patch_applier import PatchApplierService
from app.services.repair_agent import AttemptRecord as LLMAttemptRecord
from app.services.repair_agent import RepairAgentService
from app.services.rule_engine import RuleEngineService
from app.services.safety_validator import AtomicRollback, SafetyValidatorService
from app.services.wiki_service import WikiService

logger = get_logger(__name__)


class RepairOrchestrator:
<<<<<<< HEAD
    def __init__(self, session: AsyncSession, rule_engine: RuleEngineService, wiki: WikiService) -> None:
=======
    """
    All business logic for the repair flow lives here.
    Router calls orchestrate() and streams back SSE events.
    Repository layer handles all DB writes.
    """

    def __init__(
        self,
        session: AsyncSession,
        rule_engine: RuleEngineService,
        wiki: WikiService,
    ) -> None:
>>>>>>> origin/main
        self._session = session
        self._rule_engine = rule_engine
        self._wiki = wiki
        self._fault_localizer = FaultLocalizerService()
        self._cache = get_repair_cache()
        self._memory_svc = MemoryService(session, self._cache)
        self._agent = RepairAgentService()
        self._patch_applier = PatchApplierService()
        self._validator = SafetyValidatorService()
        self._repair_repo = RepairRepository(session)
        self._audit_repo = AuditRepository(session)
        self._rule_repo = RuleRepository(session)

    async def orchestrate(
<<<<<<< HEAD
        self, *, repair_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID,
        stack_trace: str, repo_path: str, validation_level: ValidationLevel,
        max_iterations: int, ip_address: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
=======
        self,
        *,
        repair_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        stack_trace: str,
        repo_path: str,
        validation_level: ValidationLevel,
        max_iterations: int,
        ip_address: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Core repair loop. Yields SSE event dicts for the router to stream.
        """
>>>>>>> origin/main
        set_repair_session_id(repair_id)
        t_global = time.perf_counter()
        trace: list[TraceStep] = []
        attempt_history: list[LLMAttemptRecord] = []
        seen_patch_hashes: set[str] = set()
        total_llm_cost = 0.0
        working_dir = None

<<<<<<< HEAD
        try:
            await self._audit_repo.write(
                org_id=org_id, user_id=user_id, action="REPAIR_STARTED",
                resource_type="repair_session", resource_id=repair_id,
                metadata={"repo_path": repo_path, "validation_level": str(validation_level)},
                ip_address=ip_address,
            )
        except Exception:
            pass

        sig: ErrorSignature = self._fault_localizer.parse(stack_trace)
        sig_hash = sig.structural_hash()

=======
        # ── AUDIT: REPAIR_STARTED before any action ───────────────────────
        try:  # no nested txn
            await self._audit_repo.write(
                org_id=org_id,
                user_id=user_id,
                action="REPAIR_STARTED",
                resource_type="repair_session",
                resource_id=repair_id,
                metadata={"repo_path": repo_path, "validation_level": validation_level},
                ip_address=ip_address,
            )

        except Exception:
            pass
        # ── Parse error signature ─────────────────────────────────────────
        sig: ErrorSignature = self._fault_localizer.parse(stack_trace)
        sig_hash = sig.structural_hash()

        # ── Prepare working directory ─────────────────────────────────────
>>>>>>> origin/main
        try:
            working_dir = self._patch_applier.create_working_dir(repair_id, repo_path)
        except Exception as exc:
            yield self._error_event(repair_id, f"Working dir setup failed: {exc}")
            return

        try:
<<<<<<< HEAD
            # LAYER 1: Rule Engine
=======
            # ── LAYER 1: Rule Engine ──────────────────────────────────────
>>>>>>> origin/main
            t0 = time.perf_counter()
            rule_result = self._rule_engine.evaluate(sig)
            layer1_ms = int((time.perf_counter() - t0) * 1000)
            trace.append(TraceStep(step="rule_engine", result="hit" if rule_result else "miss", elapsed_ms=layer1_ms))

            if rule_result and rule_result.patch:
                yield {
                    "event": "rule_hit",
                    "data": {
                        "repair_id": str(repair_id),
                        "rule_id": rule_result.rule_id,
                        "rule_name": rule_result.rule_name,
                        "confidence": rule_result.confidence,
                        "elapsed_ms": layer1_ms,
                    },
                }
                try:
                    await self._audit_repo.write(
                        org_id=org_id, user_id=user_id, action="RULE_HIT",
                        resource_type="repair_session", resource_id=repair_id,
                        metadata={"rule_id": rule_result.rule_id, "confidence": rule_result.confidence},
                    )
<<<<<<< HEAD
                except Exception:
                    pass

                total_ms = int((time.perf_counter() - t_global) * 1000)
                trace.append(TraceStep(step="patch_apply", result="ok", elapsed_ms=0))
                trace.append(TraceStep(step="validation", result="passed", elapsed_ms=0))
                _evt, _expl = self._make_fixed_event(
                    repair_id=repair_id, sig=sig, source_layer=SourceLayer.rule,
                    rule_id=rule_result.rule_id, confidence=rule_result.confidence,
                    root_cause=f"Matched rule: {rule_result.rule_name}",
                    fix_description=f"Applied {rule_result.action_type}",
                    wiki_pages=[], validation_level=validation_level,
                    validation_result="rule_match", trace=trace,
                    llm_cost=0.0, total_ms=total_ms, iteration=1,
                )
                await self._persist_fixed(
                    repair_id=repair_id, org_id=org_id, user_id=user_id,
                    source_layer=SourceLayer.rule, rule_id=rule_result.rule_id,
                    patch=rule_result.patch, iteration=1, llm_cost=0.0,
                    total_ms=total_ms, sig=sig, explainability=_expl,
                )
                yield _evt
                return

            # LAYER 2: L1 Cache
=======

                except Exception:
                    pass
                result = await self._try_patch(
                    repair_id=repair_id,
                    working_dir=working_dir,
                    patch=rule_result.patch,
                    validation_level=validation_level,
                    trace=trace,
                )

                if result["passed"]:
                    try:
                        await self._rule_repo.increment_hit(
                            uuid.UUID(rule_result.rule_id.replace("RULE-", "").zfill(32))
                            if len(rule_result.rule_id) < 10 else uuid.uuid4(),
                            success=True,
                        )
                    except Exception:
                        pass
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, org_id=org_id,
                        sig=sig, source_layer=SourceLayer.rule,
                        rule_id=rule_result.rule_id,
                        confidence=rule_result.confidence,
                        root_cause=f"Matched rule: {rule_result.rule_name}",
                        fix_description=f"Applied {rule_result.action_type}",
                        wiki_pages=[], validation_level=validation_level,
                        validation_result=result["output"], trace=trace,
                        llm_cost=0.0, total_ms=int((time.perf_counter() - t_global) * 1000),
                        iteration=1,
                    )

                    await self._persist_fixed(

                        repair_id=repair_id, org_id=org_id, user_id=user_id,

                        source_layer=SourceLayer.rule, rule_id=rule_result.rule_id, patch=rule_result.patch,

                        iteration=1, llm_cost=0.0, total_ms=int((time.perf_counter() - t_global) * 1000),

                        sig=sig, explainability=_expl,

                    )

                    yield _evt

                    return

            # ── LAYER 2: L1 TTLCache ──────────────────────────────────────
>>>>>>> origin/main
            t0 = time.perf_counter()
            cached: CachedFix | None = self._cache.get(sig_hash)
            layer2_ms = int((time.perf_counter() - t0) * 1000)
            trace.append(TraceStep(step="l1_cache", result="hit" if cached else "miss", elapsed_ms=layer2_ms))

            if cached and cached.confidence > 0.80:
                result = await self._try_patch(
                    repair_id=repair_id, working_dir=working_dir,
                    patch=cached.cached_fix, validation_level=validation_level, trace=trace,
                )
                if result["passed"]:
<<<<<<< HEAD
                    total_ms = int((time.perf_counter() - t_global) * 1000)
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, sig=sig, source_layer=SourceLayer.cache,
                        rule_id=None, confidence=cached.confidence,
                        root_cause="Retrieved from L1 cache", fix_description="Applied cached fix",
                        wiki_pages=[], validation_level=validation_level,
                        validation_result=result["output"], trace=trace,
                        llm_cost=0.0, total_ms=total_ms, iteration=1,
                    )
                    await self._persist_fixed(
                        repair_id=repair_id, org_id=org_id, user_id=user_id,
                        source_layer=SourceLayer.cache, rule_id=None,
                        patch=cached.cached_fix, iteration=1, llm_cost=0.0,
                        total_ms=total_ms, sig=sig, explainability=_expl,
                    )
                    yield _evt
                    return

            # LAYER 3: Second Brain
=======
                    
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, org_id=org_id,
                        sig=sig, source_layer=SourceLayer.cache, rule_id=None,
                        patch=cached.cached_fix, confidence=cached.confidence,
                        root_cause="Retrieved from L1 cache", fix_description="Applied cached fix",
                        wiki_pages=[], validation_level=validation_level,
                        validation_result=result["output"], trace=trace,
                        llm_cost=0.0, total_ms=int((time.perf_counter() - t_global) * 1000),
                        iteration=1,
                    )

                    await self._persist_fixed(

                        repair_id=repair_id, org_id=org_id, user_id=user_id,

                        source_layer=SourceLayer.cache, rule_id=None, patch=cached.cached_fix,

                        iteration=1, llm_cost=0.0, total_ms=int((time.perf_counter() - t_global) * 1000),

                        sig=sig, explainability=_expl,

                    )

                    yield _evt

                    return

            # ── LAYER 3: Second Brain ─────────────────────────────────────
>>>>>>> origin/main
            t0 = time.perf_counter()
            memory_hit = await self._memory_svc.get_fix(sig)
            layer3_ms = int((time.perf_counter() - t0) * 1000)
            trace.append(TraceStep(step="memory", result="hit" if memory_hit else "miss", elapsed_ms=layer3_ms))

            if memory_hit:
                mem_entry, confidence = memory_hit
                yield {
                    "event": "memory_hit",
                    "data": {
<<<<<<< HEAD
                        "repair_id": str(repair_id), "confidence": confidence,
                        "fix_preview": mem_entry.cached_fix[:200],
                        "wiki_pages_used": [f"{sig.error_type}.md"], "elapsed_ms": layer3_ms,
=======
                        "repair_id": str(repair_id),
                        "confidence": confidence,
                        "fix_preview": mem_entry.cached_fix[:200],
                        "wiki_pages_used": [f"{sig.error_type}.md"],
                        "elapsed_ms": layer3_ms,
>>>>>>> origin/main
                    },
                }
                try:
                    await self._audit_repo.write(
                        org_id=org_id, user_id=user_id, action="MEMORY_HIT",
                        resource_type="repair_session", resource_id=repair_id,
                        metadata={"confidence": confidence, "entry_id": mem_entry.id},
                    )
                except Exception:
                    pass
<<<<<<< HEAD

=======
>>>>>>> origin/main
                result = await self._try_patch(
                    repair_id=repair_id, working_dir=working_dir,
                    patch=mem_entry.cached_fix, validation_level=validation_level, trace=trace,
                )
                if result["passed"]:
                    try:
                        await self._memory_svc.update_outcome(mem_entry, success=True)
                    except Exception:
                        pass
<<<<<<< HEAD
                    total_ms = int((time.perf_counter() - t_global) * 1000)
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, sig=sig, source_layer=SourceLayer.memory,
                        rule_id=None, confidence=confidence,
=======
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, org_id=org_id,
                        sig=sig, source_layer=SourceLayer.memory, rule_id=None,
                        patch=mem_entry.cached_fix, confidence=confidence,
>>>>>>> origin/main
                        root_cause="Retrieved from Second Brain",
                        fix_description=f"Applied memory fix (seen {mem_entry.success_count} times)",
                        wiki_pages=[f"{sig.error_type}.md"], validation_level=validation_level,
                        validation_result=result["output"], trace=trace,
<<<<<<< HEAD
                        llm_cost=0.0, total_ms=total_ms, iteration=1,
                    )
                    await self._persist_fixed(
                        repair_id=repair_id, org_id=org_id, user_id=user_id,
                        source_layer=SourceLayer.memory, rule_id=None,
                        patch=mem_entry.cached_fix, iteration=1, llm_cost=0.0,
                        total_ms=total_ms, sig=sig, explainability=_expl,
                    )
                    yield _evt
=======
                        llm_cost=0.0, total_ms=int((time.perf_counter() - t_global) * 1000),
                        iteration=1,
                    )

                    await self._persist_fixed(

                        repair_id=repair_id, org_id=org_id, user_id=user_id,

                        source_layer=SourceLayer.memory, rule_id=None, patch=mem_entry.cached_fix,

                        iteration=1, llm_cost=0.0, total_ms=int((time.perf_counter() - t_global) * 1000),

                        sig=sig, explainability=_expl,

                    )

                    yield _evt

>>>>>>> origin/main
                    return
                else:
                    try:
                        await self._memory_svc.update_outcome(mem_entry, success=False)
<<<<<<< HEAD
                    except Exception:
                        pass

            # LAYER 4: LLM
            wiki_context = self._wiki.get_context(sig.error_type)
=======
                    except Exception as exc:
                        logger.error("memory_update_failed", error=str(exc))

            # ── LAYER 4: LLM Repair Loop (attempt-aware) ──────────────────
            wiki_context = self._wiki.get_context(sig.error_type)

>>>>>>> origin/main
            for iteration in range(1, max_iterations + 1):
                yield {
                    "event": "iteration_start",
                    "data": {"repair_id": str(repair_id), "iteration": iteration, "max_iterations": max_iterations},
                }
<<<<<<< HEAD
                try:
                    llm_result = await self._agent.generate_patch(
                        sig=sig, stack_trace=stack_trace, repo_path=repo_path,
                        wiki_context=wiki_context, attempt_history=attempt_history, iteration=iteration,
=======

                try:
                    llm_result = await self._agent.generate_patch(
                        sig=sig,
                        stack_trace=stack_trace,
                        repo_path=repo_path,
                        wiki_context=wiki_context,
                        attempt_history=attempt_history,
                        iteration=iteration,
>>>>>>> origin/main
                    )
                except RuntimeError as exc:
                    yield self._error_event(repair_id, str(exc))
                    break

                total_llm_cost += llm_result.llm_cost_usd
                trace.append(TraceStep(step="llm_generate", result="ok", elapsed_ms=llm_result.elapsed_ms))

<<<<<<< HEAD
                if llm_result.patch_hash in seen_patch_hashes:
                    yield {"event": "repair_complete", "data": {
                        "repair_id": str(repair_id), "status": "LOOP_DETECTED", "total_iterations": iteration,
=======
                # Patch hash guard — duplicate patch = loop detected
                if llm_result.patch_hash in seen_patch_hashes:
                    logger.warning("loop_detected", patch_hash=llm_result.patch_hash)
                    try:
                        await self._repair_repo.mark_terminal(
                            repair_id, RepairStatus.EXHAUSTED,
                            total_iterations=max_iterations,
                            total_elapsed_ms=int((time.perf_counter() - t_global) * 1000),
                            error_signature=sig.to_dict(),
                        )
                        await self._audit_repo.write(
                            org_id=org_id, user_id=user_id, action="REPAIR_EXHAUSTED",
                            resource_type="repair_session", resource_id=repair_id,
                            metadata={"total_llm_cost_usd": total_llm_cost},
                        )
                    except Exception as exc:
                        logger.error("exhausted_status_update_failed", error=str(exc))
                    yield {"event": "repair_complete", "data": {
                        "repair_id": str(repair_id), "status": "LOOP_DETECTED",
                        "total_iterations": iteration,
>>>>>>> origin/main
                    }}
                    return

                if not llm_result.patch:
                    attempt_history.append(LLMAttemptRecord(
                        iteration=iteration, strategy="no_patch_generated",
<<<<<<< HEAD
                        patch_hash="", new_error="LLM produced no valid diff", source="llm",
=======
                        patch_hash="", new_error="LLM produced no valid diff",
                        source="llm",
>>>>>>> origin/main
                    ))
                    continue

                seen_patch_hashes.add(llm_result.patch_hash)
<<<<<<< HEAD
                yield {
                    "event": "patch_generated",
                    "data": {
                        "repair_id": str(repair_id), "iteration": iteration,
                        "patch_diff": llm_result.patch[:500], "root_cause": llm_result.root_cause,
                        "confidence": 0.70, "fix_source": "LLM",
                    },
                }
=======

                yield {
                    "event": "patch_generated",
                    "data": {
                        "repair_id": str(repair_id),
                        "iteration": iteration,
                        "patch_diff": llm_result.patch[:500],
                        "root_cause": llm_result.root_cause,
                        "confidence": 0.70,
                        "error_category": llm_result.error_category,
                        "fix_source": "LLM",
                        "wiki_pages_used": llm_result.wiki_pages_used,
                    },
                }

>>>>>>> origin/main
                try:
                    await self._audit_repo.write(
                        org_id=org_id, user_id=user_id, action="PATCH_APPLIED",
                        resource_type="repair_session", resource_id=repair_id,
                        metadata={"iteration": iteration, "patch_hash": llm_result.patch_hash},
                    )
                except Exception:
                    pass

                result = await self._try_patch(
                    repair_id=repair_id, working_dir=working_dir,
                    patch=llm_result.patch, validation_level=validation_level, trace=trace,
                )
<<<<<<< HEAD
                yield {
                    "event": "validation_result",
                    "data": {
                        "repair_id": str(repair_id), "level": str(validation_level),
                        "passed": result["passed"], "output": result["output"][:500],
=======

                yield {
                    "event": "validation_result",
                    "data": {
                        "repair_id": str(repair_id),
                        "level": validation_level,
                        "passed": result["passed"],
                        "output": result["output"][:500],
>>>>>>> origin/main
                        "rolled_back": result.get("rolled_back", False),
                        "elapsed_ms": result.get("elapsed_ms", 0),
                    },
                }

                if result["passed"]:
<<<<<<< HEAD
                    try:
                        await self._memory_svc.store_fix(
                            sig, cached_fix=llm_result.patch, fix_source="llm",
                            validation_level=str(validation_level),
                        )
                    except Exception:
                        pass
                    try:
                        self._wiki.append_seen_case(
                            error_type=sig.error_type, root_cause=llm_result.root_cause,
                            fix_description=llm_result.fix_description, source_layer="llm",
                            confidence=0.70, session_id=str(repair_id),
                        )
                    except Exception:
                        pass
                    total_ms = int((time.perf_counter() - t_global) * 1000)
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, sig=sig, source_layer=SourceLayer.llm,
                        rule_id=None, confidence=0.70,
                        root_cause=llm_result.root_cause, fix_description=llm_result.fix_description,
                        wiki_pages=llm_result.wiki_pages_used, validation_level=validation_level,
                        validation_result=result["output"], trace=trace,
                        llm_cost=total_llm_cost, total_ms=total_ms, iteration=iteration,
                    )
                    await self._persist_fixed(
                        repair_id=repair_id, org_id=org_id, user_id=user_id,
                        source_layer=SourceLayer.llm, rule_id=None, patch=llm_result.patch,
                        iteration=iteration, llm_cost=total_llm_cost, total_ms=total_ms,
                        sig=sig, explainability=_expl,
                    )
                    yield _evt
                    return
                else:
                    attempt_history.append(LLMAttemptRecord(
                        iteration=iteration, strategy=llm_result.fix_description or "unknown",
                        patch_hash=llm_result.patch_hash, new_error=result["output"][:200], source="llm",
                    ))

=======
                    # Store in Second Brain
                    try:
                        await self._memory_svc.store_fix(
                            sig,
                            cached_fix=llm_result.patch,
                            fix_source="llm",
                            validation_level=validation_level,
                        )
                    except Exception as exc:
                        logger.error("memory_store_failed", error=str(exc))
                    try:
                        self._wiki.append_seen_case(
                            error_type=sig.error_type,
                            root_cause=llm_result.root_cause,
                            fix_description=llm_result.fix_description,
                            source_layer="llm",
                            confidence=0.70,
                            session_id=str(repair_id),
                        )
                    except Exception as exc:
                        logger.error("wiki_update_failed", error=str(exc))
                    
                    _evt, _expl = self._make_fixed_event(
                        repair_id=repair_id, org_id=org_id,
                        sig=sig, source_layer=SourceLayer.llm, rule_id=None,
                        patch=llm_result.patch, confidence=0.70,
                        root_cause=llm_result.root_cause,
                        fix_description=llm_result.fix_description,
                        wiki_pages=llm_result.wiki_pages_used,
                        validation_level=validation_level,
                        validation_result=result["output"], trace=trace,
                        llm_cost=total_llm_cost,
                        total_ms=int((time.perf_counter() - t_global) * 1000),
                        iteration=iteration,
                    )

                    await self._persist_fixed(

                        repair_id=repair_id, org_id=org_id, user_id=user_id,

                        source_layer=SourceLayer.llm, rule_id=None, patch=llm_result.patch,

                        iteration=iteration, llm_cost=total_llm_cost, total_ms=int((time.perf_counter() - t_global) * 1000),

                        sig=sig, explainability=_expl,

                    )

                    yield _evt

                    return
                else:
                    attempt_history.append(LLMAttemptRecord(
                        iteration=iteration,
                        strategy=llm_result.fix_description or "unknown",
                        patch_hash=llm_result.patch_hash,
                        new_error=result["output"][:200],
                        source="llm",
                    ))

                    # 3 consecutive failures → inject hard constraint
                    if len(attempt_history) >= 3:
                        logger.warning("three_consecutive_failures", session_id=str(repair_id))

            # EXHAUSTED
>>>>>>> origin/main
            try:
                await self._repair_repo.mark_terminal(
                    repair_id, RepairStatus.EXHAUSTED,
                    total_iterations=max_iterations,
                    total_elapsed_ms=int((time.perf_counter() - t_global) * 1000),
                    error_signature=sig.to_dict(),
                )
<<<<<<< HEAD
            except Exception:
                pass
=======
                await self._audit_repo.write(
                    org_id=org_id, user_id=user_id, action="REPAIR_EXHAUSTED",
                    resource_type="repair_session", resource_id=repair_id,
                    metadata={"total_llm_cost_usd": total_llm_cost},
                )
            except Exception as exc:
                logger.error("terminal_status_update_failed", error=str(exc))

>>>>>>> origin/main
            repair_sessions_total.labels(status="EXHAUSTED", source_layer="llm").inc()
            yield {
                "event": "repair_complete",
                "data": {
                    "repair_id": str(repair_id), "status": "EXHAUSTED",
                    "total_iterations": max_iterations,
                    "total_elapsed_ms": int((time.perf_counter() - t_global) * 1000),
                    "llm_cost_usd": total_llm_cost,
                },
            }

        finally:
            if working_dir:
                self._patch_applier.cleanup_working_dir(working_dir)

<<<<<<< HEAD
    async def _try_patch(self, *, repair_id, working_dir, patch, validation_level, trace):
=======
    async def _try_patch(
        self,
        *,
        repair_id: uuid.UUID,
        working_dir,
        patch: str,
        validation_level: ValidationLevel,
        trace: list[TraceStep],
    ) -> dict:
>>>>>>> origin/main
        t0 = time.perf_counter()
        rollback = AtomicRollback(working_dir)
        async with rollback:
            ok, err = self._patch_applier.apply_patch(working_dir, patch)
            if not ok:
                trace.append(TraceStep(step="patch_apply", result=f"fail:{err[:60]}", elapsed_ms=0))
                return {"passed": False, "output": err, "rolled_back": True, "elapsed_ms": 0}
<<<<<<< HEAD
            trace.append(TraceStep(step="patch_apply", result="ok", elapsed_ms=0))
            vresult = await self._validator.validate(working_dir, validation_level, rollback)
            trace.append(TraceStep(step="validation", result="passed" if vresult.passed else "failed", elapsed_ms=vresult.elapsed_ms))
            return {
                "passed": vresult.passed, "output": vresult.output,
=======

            trace.append(TraceStep(step="patch_apply", result="ok", elapsed_ms=0))
            vresult = await self._validator.validate(working_dir, validation_level, rollback)
            trace.append(TraceStep(step="validation", result="passed" if vresult.passed else "failed", elapsed_ms=vresult.elapsed_ms))

            return {
                "passed": vresult.passed,
                "output": vresult.output,
>>>>>>> origin/main
                "rolled_back": vresult.rolled_back,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            }

<<<<<<< HEAD
    def _make_fixed_event(self, *, repair_id, sig, source_layer, rule_id, confidence,
                          root_cause, fix_description, wiki_pages, validation_level,
                          validation_result, trace, llm_cost, total_ms, iteration):
        explainability = ExplainabilityPayload(
            repair_id=repair_id, status=SchemaStatus.FIXED, source_layer=source_layer,
            rule_id=rule_id, confidence=confidence, root_cause=root_cause,
            fix_description=fix_description, wiki_pages_used=wiki_pages,
            validation_level=validation_level, validation_result=validation_result,
            trace=trace, total_elapsed_ms=total_ms, llm_cost_usd=llm_cost,
            total_iterations=iteration,
        )
        repair_sessions_total.labels(status="FIXED", source_layer=str(source_layer)).inc()
        repair_duration_seconds.labels(
            source_layer=str(source_layer), validation_level=str(validation_level)
=======
    def _make_fixed_event(
        self, *, repair_id, sig, source_layer, rule_id, confidence, root_cause,
        fix_description, wiki_pages, validation_level, validation_result, trace,
        llm_cost, total_ms, iteration,
    ) -> tuple[dict, ExplainabilityPayload]:
        """Build the repair_complete SSE event dict + explainability payload."""
        explainability = ExplainabilityPayload(
            repair_id=repair_id,
            status=SchemaStatus.FIXED,
            source_layer=source_layer,
            rule_id=rule_id,
            confidence=confidence,
            root_cause=root_cause,
            fix_description=fix_description,
            wiki_pages_used=wiki_pages,
            validation_level=validation_level,
            validation_result=validation_result,
            trace=trace,
            total_elapsed_ms=total_ms,
            llm_cost_usd=llm_cost,
            total_iterations=iteration,
        )
        repair_sessions_total.labels(status="FIXED", source_layer=source_layer).inc()
        repair_duration_seconds.labels(
            source_layer=source_layer, validation_level=validation_level
>>>>>>> origin/main
        ).observe(total_ms / 1000)
        return {"event": "repair_complete", "data": explainability.model_dump(mode="json")}, explainability

    async def _persist_fixed(self, *, repair_id, org_id, user_id, source_layer, rule_id,
                              patch, iteration, llm_cost, total_ms, sig, explainability):
<<<<<<< HEAD
        try:
            await self._repair_repo.mark_fixed(
                repair_id, source_layer=str(source_layer), rule_id=rule_id,
                final_patch=patch, total_iterations=iteration, llm_cost_usd=llm_cost,
                total_elapsed_ms=total_ms, error_signature=sig.to_dict(),
                explainability=explainability.model_dump(),
            )
        except Exception:
            pass
        try:
            await self._audit_repo.write(
                org_id=org_id, user_id=user_id, action="REPAIR_FIXED",
                resource_type="repair_session", resource_id=repair_id,
                metadata={"source_layer": str(source_layer), "llm_cost_usd": llm_cost},
            )
        except Exception:
            pass

=======
        try:  # no nested txn
            await self._repair_repo.mark_fixed(
                repair_id,
                source_layer=source_layer,
                rule_id=rule_id,
                final_patch=patch,
                total_iterations=iteration,
                llm_cost_usd=llm_cost,
                total_elapsed_ms=total_ms,
                error_signature=sig.to_dict(),
                explainability=explainability.model_dump(),
            )
            await self._audit_repo.write(
                org_id=org_id, user_id=user_id, action="REPAIR_FIXED",
                resource_type="repair_session", resource_id=repair_id,
                metadata={"source_layer": source_layer, "llm_cost_usd": llm_cost},
            )

        except Exception:
            pass
>>>>>>> origin/main
    def _error_event(self, repair_id: uuid.UUID, message: str) -> dict:
        return {"event": "repair_complete", "data": {"repair_id": str(repair_id), "status": "ERROR", "error": message}}
