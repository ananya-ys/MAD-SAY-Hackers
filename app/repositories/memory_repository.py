"""
app/repositories/memory_repository.py
Second Brain DB access.
CRITICAL: SELECT FOR UPDATE on confidence updates — concurrent repair
sessions must not race on the same memory entry.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_entry import MemoryEntry


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(self, structural_hash: str) -> MemoryEntry | None:
        result = await self._session.execute(
            select(MemoryEntry).where(MemoryEntry.structural_hash == structural_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_error_type(self, error_type: str, min_confidence: float = 0.0) -> list[MemoryEntry]:
        """
        Fuzzy match candidates — same error_type, above confidence floor.
        Ordered by confidence DESC to short-circuit on first match above threshold.
        Anti-N+1: single query returns all candidates for this error class.
        """
        result = await self._session.execute(
            select(MemoryEntry)
            .where(
                and_(
                    MemoryEntry.error_type == error_type,
                    MemoryEntry.confidence >= min_confidence,
                )
            )
            .order_by(desc(MemoryEntry.confidence))
            .limit(20)  # cap fuzzy scan
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        structural_hash: str,
        signature_json: dict,
        error_type: str,
        cached_fix: str,
        fix_source: str,
        validation_level: str,
        initial_confidence: float = 0.70,
    ) -> MemoryEntry:
        existing = await self.get_by_hash(structural_hash)
        if existing:
            return existing

        entry = MemoryEntry(
            structural_hash=structural_hash,
            signature_json=signature_json,
            error_type=error_type,
            cached_fix=cached_fix,
            fix_source=fix_source,
            validation_level=validation_level,
            confidence=initial_confidence,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def update_outcome(
        self,
        entry_id: int,
        *,
        success: bool,
        new_confidence: float,
    ) -> None:
        """
        SELECT FOR UPDATE — prevents concurrent sessions from racing
        on success_count / failure_count for the same error signature.
        """
        result = await self._session.execute(
            select(MemoryEntry)
            .where(MemoryEntry.id == entry_id)
            .with_for_update()
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return

        if success:
            entry.success_count += 1
        else:
            entry.failure_count += 1

        entry.confidence = new_confidence
        entry.last_used_at = datetime.utcnow()
        await self._session.flush()

    async def evict(self, entry_id: int) -> None:
        result = await self._session.execute(
            select(MemoryEntry).where(MemoryEntry.id == entry_id).with_for_update()
        )
        entry = result.scalar_one_or_none()
        if entry:
            await self._session.delete(entry)
            await self._session.flush()

    async def get_stats(self) -> dict:
        result = await self._session.execute(select(MemoryEntry))
        entries = result.scalars().all()
        if not entries:
            return {"total": 0, "avg_confidence": 0.0}
        confs = [e.confidence for e in entries]
        return {
            "total": len(entries),
            "avg_confidence": round(sum(confs) / len(confs), 4),
        }

    async def get_eviction_candidates(self, threshold: float) -> list[MemoryEntry]:
        result = await self._session.execute(
            select(MemoryEntry)
            .where(MemoryEntry.confidence <= threshold)
            .order_by(asc(MemoryEntry.confidence))
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_all(self, min_confidence: float = 0.0, limit: int = 500) -> list[MemoryEntry]:
        """
        Return all memory entries above a confidence floor.
        Single query — no hardcoded error-type scan needed in the router.
        Ordered by confidence DESC.
        """
        result = await self._session.execute(
            select(MemoryEntry)
            .where(MemoryEntry.confidence >= min_confidence)
            .order_by(desc(MemoryEntry.confidence))
            .limit(limit)
        )
        return list(result.scalars().all())
