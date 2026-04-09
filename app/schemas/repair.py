"""
app/schemas/repair.py
Pydantic v2 schemas for repair API — request and response separated.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ValidationLevel(str, Enum):
    BASIC = "BASIC"
    ENDPOINT = "ENDPOINT"
    TESTS = "TESTS"


class RepairStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    EXHAUSTED = "EXHAUSTED"
    ERROR = "ERROR"
    LOOP_DETECTED = "LOOP_DETECTED"


class SourceLayer(str, Enum):
    rule = "rule"
    cache = "cache"
    memory = "memory"
    llm = "llm"
    unknown = "unknown"


# ── Request ──────────────────────────────────────────────────────────────────

class RepairRequest(BaseModel):
    stack_trace: str = Field(..., min_length=10, max_length=51200)
    repo_path: str = Field(..., min_length=1, max_length=1024)
    validation_level: ValidationLevel = ValidationLevel.BASIC
    max_iterations: int = Field(default=5, ge=1, le=7)

    @field_validator("stack_trace")
    @classmethod
    def no_binary_content(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("stack_trace must not contain null bytes")
        return v.strip()


# ── SSE Event payloads ───────────────────────────────────────────────────────

class TraceStep(BaseModel):
    step: str
    result: str
    elapsed_ms: int


class ExplainabilityPayload(BaseModel):
    repair_id: UUID
    status: RepairStatus
    source_layer: SourceLayer
    rule_id: str | None = None
    confidence: float | None = None
    root_cause: str | None = None
    error_category: str | None = None
    fix_description: str | None = None
    fix_source: str | None = None
    wiki_pages_used: list[str] = Field(default_factory=list)
    validation_level: ValidationLevel | None = None
    validation_result: str | None = None
    trace: list[TraceStep] = Field(default_factory=list)
    total_elapsed_ms: int = 0
    llm_cost_usd: float = 0.0
    total_iterations: int = 0


class SSEEvent(BaseModel):
    event: str
    data: dict[str, Any]


# ── Response models ──────────────────────────────────────────────────────────

class RepairSummary(BaseModel):
    id: UUID
    status: RepairStatus
    source_layer: SourceLayer | None
    rule_id: str | None
    validation_level: ValidationLevel
    total_iterations: int
    llm_cost_usd: float
    total_elapsed_ms: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AttemptRecord(BaseModel):
    iteration: int
    strategy: str
    patch_hash: str
    new_error: str
    source: SourceLayer


class RepairDetail(BaseModel):
    id: UUID
    status: RepairStatus
    source_layer: SourceLayer | None
    stack_trace: str
    repo_path: str
    error_signature: dict
    validation_level: ValidationLevel
    max_iterations: int
    total_iterations: int
    final_patch: str | None
    llm_cost_usd: float
    total_elapsed_ms: int | None
    explainability: dict | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PaginatedRepairs(BaseModel):
    items: list[RepairSummary]
    total: int
    page: int
    limit: int
