"""app/repositories/rule_repository.py — Rule Engine DB access."""
from __future__ import annotations

import uuid

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule


class RuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_rules(self, org_id: uuid.UUID | None = None) -> list[Rule]:
        """
        Return builtin rules + org-specific rules.
        Ordered by confidence DESC — higher confidence rules evaluated first.
        """
        filters = [Rule.is_active.is_(True), Rule.deleted_at.is_(None)]
        if org_id:
            filters.append(
                (Rule.org_id == org_id) | Rule.org_id.is_(None)
            )
        else:
            filters.append(Rule.org_id.is_(None))

        result = await self._session.execute(
            select(Rule).where(and_(*filters)).order_by(desc(Rule.confidence))
        )
        return list(result.scalars().all())

    async def get_by_id(self, rule_id: uuid.UUID) -> Rule | None:
        result = await self._session.execute(select(Rule).where(Rule.id == rule_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        org_id: uuid.UUID,
        name: str,
        description: str | None,
        condition_yaml: str,
        action_type: str,
        action_params: dict | None,
        confidence: float,
        created_by: uuid.UUID,
    ) -> Rule:
        rule = Rule(
            org_id=org_id,
            name=name,
            description=description,
            condition_yaml=condition_yaml,
            action_type=action_type,
            action_params=action_params,
            confidence=confidence,
            created_by=created_by,
            source="org",
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def increment_hit(self, rule_id: uuid.UUID, *, success: bool) -> None:
        values: dict = {"hit_count": Rule.hit_count + 1}
        if success:
            values["success_count"] = Rule.success_count + 1
        else:
            values["failure_count"] = Rule.failure_count + 1
        await self._session.execute(
            update(Rule).where(Rule.id == rule_id).values(**values)
        )

    async def soft_delete(self, rule_id: uuid.UUID) -> None:
        from datetime import datetime
        await self._session.execute(
            update(Rule)
            .where(Rule.id == rule_id)
            .values(is_active=False, deleted_at=datetime.utcnow())
        )
