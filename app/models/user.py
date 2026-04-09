"""app/models/user.py — User ORM model."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, PyEnum):
    ENGINEER = "ENGINEER"
    SRE = "SRE"
    ADMIN = "ADMIN"
    CI_AGENT = "CI_AGENT"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserRole.ENGINEER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    refresh_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)  # revocation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    repair_sessions: Mapped[list] = relationship("RepairSession", back_populates="user", lazy="noload")
