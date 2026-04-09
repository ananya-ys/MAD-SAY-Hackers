"""
app/services/memory_service.py
Layer 3: Second Brain — semantic memory lookup using structural_hash (exact)
and similar() (fuzzy). Confidence gated at 0.80 for auto-use.
Confidence formula: success_rate×0.50 + recency_score×0.20 + frequency_w×0.30
"""
from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import confidence_histogram, memory_hits_total
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository
from app.schemas.error_signature import ErrorSignature
from app.services.cache_service import CachedFix, RepairCacheService

logger = get_logger(__name__)


def compute_confidence(entry: MemoryEntry) -> float:
    """
    Weighted confidence score — never a naive counter.

    success_rate  = success_count / max(total_count, 1)
    recency_score = exp(-0.01 * days_since_last_use)   # decays over ~100 days
    frequency_w   = min(total_count / 10.0, 1.0)       # caps at 10 uses
    effective_freq = frequency_w * success_rate         # zero successes → zero freq contribution

    confidence = success_rate × 0.50 + recency_score × 0.20 + effective_freq × 0.30

    KEY: frequency is weighted by success_rate. A fix tried 10 times with 0 successes
    contributes 0 from the frequency component — ensuring high-failure entries can decay
    below EVICTION_THRESHOLD (0.20) and get removed from memory.
    """
    total = entry.success_count + entry.failure_count
    success_rate = entry.success_count / max(total, 1)

    reference_dt = entry.last_used_at or entry.created_at
    days_idle = (datetime.utcnow() - reference_dt).days
    recency_score = math.exp(-0.01 * days_idle)

    frequency_w = min(total / 10.0, 1.0)
    effective_freq = frequency_w * success_rate  # penalises all-failure entries

    return round(
        success_rate * 0.50 + recency_score * 0.20 + effective_freq * 0.30,
        4,
    )


class MemoryService:
    """
    Layer 3: Semantic memory lookup.
    Exact structural_hash → fuzzy similar() → MISS.
    Confidence gate: > 0.80 auto-use, 0.60–0.80 warn, < 0.60 → LLM.
    """

    def __init__(
        self,
        session: AsyncSession,
        l1_cache: RepairCacheService,
    ) -> None:
        self._repo = MemoryRepository(session)
        self._cache = l1_cache

    async def get_fix(self, sig: ErrorSignature) -> tuple[MemoryEntry, float] | None:
        """
        Returns (entry, confidence) if confidence > CONFIDENCE_WARN threshold.
        Returns None on MISS or low confidence.
        """
        sig_hash = sig.structural_hash()

        # ── 1. Exact hash lookup ──────────────────────────────────────────
        exact = await self._repo.get_by_hash(sig_hash)
        if exact:
            conf = compute_confidence(exact)
            confidence_histogram.observe(conf)
            if conf > settings.confidence_warn:
                memory_hits_total.labels(match_type="exact").inc()
                logger.info("memory_hit_exact", sig_hash=sig_hash, confidence=conf)
                return exact, conf

        # ── 2. Fuzzy match over same error_type ──────────────────────────
        candidates = await self._repo.get_by_error_type(
            sig.error_type,
            min_confidence=settings.confidence_warn,
        )
        for entry in candidates:
            stored_sig = ErrorSignature.from_dict(entry.signature_json)
            if sig.similar(stored_sig, threshold=0.75):
                conf = compute_confidence(entry)
                confidence_histogram.observe(conf)
                if conf > settings.confidence_warn:
                    memory_hits_total.labels(match_type="fuzzy").inc()
                    logger.info(
                        "memory_hit_fuzzy",
                        entry_id=entry.id,
                        confidence=conf,
                        error_type=sig.error_type,
                    )
                    return entry, conf

        return None  # MISS → Layer 4 (LLM)

    async def store_fix(
        self,
        sig: ErrorSignature,
        *,
        cached_fix: str,
        fix_source: str,
        validation_level: str,
    ) -> MemoryEntry:
        """Store a validated fix in the Second Brain. Called after FIXED outcome."""
        entry = await self._repo.upsert(
            structural_hash=sig.structural_hash(),
            signature_json=sig.to_dict(),
            error_type=sig.error_type,
            cached_fix=cached_fix,
            fix_source=fix_source,
            validation_level=validation_level,
            initial_confidence=0.70,
        )
        # Populate L1 cache immediately
        self._cache.put(
            sig.structural_hash(),
            CachedFix(
                structural_hash=sig.structural_hash(),
                cached_fix=cached_fix,
                confidence=entry.confidence,
                fix_source=fix_source,
                memory_entry_id=entry.id,
            ),
        )
        return entry

    async def update_outcome(self, entry: MemoryEntry, *, success: bool) -> None:
        """
        Update success/failure counts and recompute confidence.
        Evict from L1 cache if confidence drops below EVICTION_THRESHOLD.
        Alert threshold: SRE notification if confidence < 0.50 (LEARNING_ALERT).
        """
        # Temporarily mutate for formula computation
        if success:
            entry.success_count += 1
        else:
            entry.failure_count += 1

        new_conf = compute_confidence(entry)
        await self._repo.update_outcome(entry.id, success=success, new_confidence=new_conf)

        logger.info(
            "memory_confidence_updated",
            entry_id=entry.id,
            success=success,
            new_confidence=new_conf,
        )

        if new_conf <= settings.confidence_eviction:
            self._cache.evict(entry.structural_hash)
            await self._repo.evict(entry.id)
            logger.warning("memory_entry_evicted", entry_id=entry.id, confidence=new_conf)

        elif new_conf <= settings.confidence_sre_alert:
            logger.warning(
                "memory_confidence_alert",
                entry_id=entry.id,
                confidence=new_conf,
                alert="SRE_REVIEW_REQUIRED",
            )

    async def get_stats(self) -> dict:
        db_stats = await self._repo.get_stats()
        return {**db_stats, **self._cache.stats()}
