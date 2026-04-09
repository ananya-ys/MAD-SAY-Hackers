"""
app/repositories/repair_repository.py
DB access only. No business logic. No layer crossings.
All queries enforce org_id isolation — EoP mitigation from STRIDE §8.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repair_session import RepairSession, RepairStatus, SourceLayer


class RepairRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        stack_trace: str,
        repo_path: str,
        validation_level: str,
        max_iterations: int,
    ) -> RepairSession:
        session = RepairSession(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            status=RepairStatus.IN_PROGRESS,
            stack_trace=stack_trace,
            repo_path=repo_path,
            validation_level=validation_level,
            max_iterations=max_iterations,
        )
        self._session.add(session)
        await self._session.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID, org_id: uuid.UUID) -> RepairSession | None:
        """org_id enforced on every query — never trust caller-supplied org from payload."""
        result = await self._session.execute(
            select(RepairSession).where(
                and_(
                    RepairSession.id == session_id,
                    RepairSession.org_id == org_id,
                    RepairSession.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None = None,  # None = SRE/ADMIN sees all
        status: str | None = None,
        source_layer: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[RepairSession], int]:
        filters = [RepairSession.org_id == org_id, RepairSession.deleted_at.is_(None)]
        if user_id:
            filters.append(RepairSession.user_id == user_id)
        if status:
            filters.append(RepairSession.status == status)
        if source_layer:
            filters.append(RepairSession.source_layer == source_layer)

        count_q = select(RepairSession).where(and_(*filters))
        rows = (await self._session.execute(count_q)).scalars().all()
        total = len(rows)

        q = (
            select(RepairSession)
            .where(and_(*filters))
            .order_by(RepairSession.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = (await self._session.execute(q)).scalars().all()
        return list(result), total

    async def mark_fixed(
        self,
        session_id: uuid.UUID,
        *,
        source_layer: str,
        rule_id: str | None,
        final_patch: str,
        total_iterations: int,
        llm_cost_usd: float,
        total_elapsed_ms: int,
        error_signature: dict,
        explainability: dict,
    ) -> None:
        await self._session.execute(
            update(RepairSession)
            .where(RepairSession.id == session_id)
            .values(
                status=RepairStatus.FIXED,
                source_layer=source_layer,
                rule_id=rule_id,
                final_patch=final_patch,
                total_iterations=total_iterations,
                llm_cost_usd=llm_cost_usd,
                total_elapsed_ms=total_elapsed_ms,
                error_signature=error_signature,
                explainability=explainability,
                completed_at=datetime.utcnow(),
            )
        )

    async def mark_terminal(
        self,
        session_id: uuid.UUID,
        status: RepairStatus,
        *,
        total_iterations: int,
        total_elapsed_ms: int,
        error_signature: dict | None = None,
        explainability: dict | None = None,
    ) -> None:
        values: dict = {
            "status": status,
            "total_iterations": total_iterations,
            "total_elapsed_ms": total_elapsed_ms,
            "completed_at": datetime.utcnow(),
        }
        if error_signature:
            values["error_signature"] = error_signature
        if explainability:
            values["explainability"] = explainability
        await self._session.execute(
            update(RepairSession).where(RepairSession.id == session_id).values(**values)
        )
