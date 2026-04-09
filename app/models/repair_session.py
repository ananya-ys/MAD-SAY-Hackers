import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class RepairStatus(str, PyEnum):
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    EXHAUSTED = "EXHAUSTED"
    ERROR = "ERROR"
    LOOP_DETECTED = "LOOP_DETECTED"

class SourceLayer(str, PyEnum):
    rule = "rule"
    cache = "cache"
    memory = "memory"
    llm = "llm"
    unknown = "unknown"

class ValidationLevelDB(str, PyEnum):
    BASIC = "BASIC"
    ENDPOINT = "ENDPOINT"
    TESTS = "TESTS"

class RepairSession(Base):
    __tablename__ = "repair_sessions"
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RepairStatus.IN_PROGRESS)
    source_layer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stack_trace: Mapped[str] = mapped_column(Text, nullable=False)
    repo_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    error_signature: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_level: Mapped[str] = mapped_column(String(16), nullable=False, default=ValidationLevelDB.BASIC)
    max_iterations: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    total_iterations: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    final_patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0, nullable=False)
    total_elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explainability: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped["User"] = relationship("User", back_populates="repair_sessions", lazy="noload")
