"""
app/repositories/audit_repository.py
Append-only audit log repository.
CRITICAL PATTERN: Audit log written BEFORE every agent action, inside the SAME transaction.
Never update. Never delete.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog

logger = get_logger(__name__)


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        *,
        org_id: uuid.UUID,
        action: str,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        api_key_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        flush: bool = True,
    ) -> AuditLog:
        """
        Append an audit log entry.
        flush=True ensures the row is written before the caller continues
        (still within the same transaction — no commit here).
        """
        entry = AuditLog(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata,
            ip_address=ip_address,
        )
        self._session.add(entry)
        if flush:
            await self._session.flush()
        logger.info("audit_written", action=action, resource_type=resource_type, resource_id=str(resource_id))
        return entry
