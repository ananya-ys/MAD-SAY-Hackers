"""app/models/rule.py — Rule Engine rule ORM model."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL = builtin rule shipped with the system
    org_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Declarative condition on ErrorSignature fields (sandboxed evaluator — no arbitrary code)
    condition_yaml: Mapped[str] = mapped_column(Text, nullable=False)

    # ADD_PACKAGE | CORRECT_TYPO | ADD_ENV_VAR | FIX_IMPORT | FIX_SYNTAX | ADD_NONE_GUARD
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="builtin", nullable=False)  # builtin | org

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
