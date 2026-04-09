"""
app/models/audit_log.py
Immutable audit log — NO UPDATE, NO DELETE. Append-only.
Written BEFORE every agent action inside the same DB transaction.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    # Actions from PRD §7.4
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # REPAIR_STARTED | RULE_HIT | MEMORY_HIT | PATCH_APPLIED
    # VALIDATION_PASSED | VALIDATION_FAILED | PATCH_ROLLED_BACK
    # REPAIR_FIXED | REPAIR_EXHAUSTED | RULE_CREATED | MEMORY_EVICTED

    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Store as TEXT for SQLite compat; PostgreSQL gets INET
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
