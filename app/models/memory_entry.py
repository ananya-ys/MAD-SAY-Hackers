"""app/models/memory_entry.py — Second Brain memory store ORM model."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Structural hash — identity key for exact lookup
    structural_hash: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)

    # Full ErrorSignature for fuzzy matching
    signature_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Denormalised for fast fuzzy-match query: WHERE error_type = :type
    error_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    cached_fix: Mapped[str] = mapped_column(Text, nullable=False)   # unified diff
    fix_source: Mapped[str] = mapped_column(String(32), default="llm", nullable=False)  # llm | rule
    validation_level: Mapped[str] = mapped_column(String(16), nullable=False)

    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # confidence stored for quick reads; recomputed on update via formula
    confidence: Mapped[float] = mapped_column(Float, default=0.70, nullable=False)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
