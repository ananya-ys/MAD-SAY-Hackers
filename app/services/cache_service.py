"""
app/services/cache_service.py
Layer 2 (L1): In-process TTLCache — sits above SQLite, eliminates DB round-trip for hot errors.
< 1ms. No Redis needed at MVP scale (< 500 RPS).
Singleton shared across all repair sessions on the same process.
"""
from __future__ import annotations

from dataclasses import dataclass

from cachetools import TTLCache

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import cache_hit_rate, cache_hits_total, cache_misses_total

logger = get_logger(__name__)


@dataclass
class CachedFix:
    structural_hash: str
    cached_fix: str          # unified diff
    confidence: float
    fix_source: str          # llm | rule
    memory_entry_id: int     # DB id — used for outcome update


class RepairCacheService:
    """
    TTLCache singleton.
    evict() called when memory confidence drops below EVICTION_THRESHOLD.
    """

    def __init__(self) -> None:
        self._cache: TTLCache = TTLCache(
            maxsize=settings.l1_cache_maxsize,
            ttl=settings.l1_cache_ttl_seconds,
        )
        self._hits = 0
        self._misses = 0

    def get(self, sig_hash: str) -> CachedFix | None:
        result = self._cache.get(sig_hash)
        if result is not None:
            self._hits += 1
            cache_hits_total.inc()
            self._update_hit_rate()
            logger.debug("l1_cache_hit", sig_hash=sig_hash)
            return result

        self._misses += 1
        cache_misses_total.inc()
        self._update_hit_rate()
        return None

    def put(self, sig_hash: str, fix: CachedFix) -> None:
        self._cache[sig_hash] = fix
        logger.debug("l1_cache_put", sig_hash=sig_hash, confidence=fix.confidence)

    def evict(self, sig_hash: str) -> None:
        """
        Called when memory confidence drops below 0.50.
        Stale fix removed from cache — next request hits SQLite.
        """
        removed = self._cache.pop(sig_hash, None)
        if removed:
            logger.info("l1_cache_evict", sig_hash=sig_hash)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def _update_hit_rate(self) -> None:
        cache_hit_rate.set(self.hit_rate)

    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "maxsize": self._cache.maxsize,
            "ttl_seconds": self._cache.ttl,
            "hit_rate": round(self.hit_rate, 4),
            "hits": self._hits,
            "misses": self._misses,
        }


# Singleton — one per process
_repair_cache = RepairCacheService()


def get_repair_cache() -> RepairCacheService:
    return _repair_cache
