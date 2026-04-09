from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.models.memory_entry import MemoryEntry
from app.models.user import UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.cache_service import get_repair_cache

router = APIRouter(prefix="/memory", tags=["memory"])

class MemoryEntryResponse(BaseModel):
    id: int
    structural_hash: str
    error_type: str
    fix_source: str
    validation_level: str
    success_count: int
    failure_count: int
    confidence: float
    model_config = {"from_attributes": True}

@router.get("", response_model=dict)
async def list_memory(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    min_confidence: float = 0.0,
) -> dict:
    repo = MemoryRepository(db)
    entries = await repo.get_all(min_confidence=min_confidence)
    return {"items": [MemoryEntryResponse.model_validate(e) for e in entries], "total": len(entries)}

@router.get("/stats")
async def memory_stats(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    repo = MemoryRepository(db)
    db_stats = await repo.get_stats()
    cache = get_repair_cache()
    return {**db_stats, "cache_hit_rate": cache.hit_rate, "cache_size": cache.stats()["size"]}

@router.delete("/{entry_id}")
async def evict_memory(
    entry_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Response:
    if current_user.role not in (UserRole.SRE.value, UserRole.ADMIN.value):
        raise HTTPException(403, "SRE or ADMIN required")
    async with db.begin():
        result = await db.execute(select(MemoryEntry).where(MemoryEntry.id == entry_id))
        entry = result.scalar_one_or_none()
        if not entry:
            raise HTTPException(404, "Memory entry not found")
        get_repair_cache().evict(entry.structural_hash)
        await MemoryRepository(db).evict(entry_id)
        await AuditRepository(db).write(
            org_id=current_user.org_id, user_id=current_user.id,
            action="MEMORY_EVICTED", resource_type="memory_entry",
            resource_id=uuid.uuid4(),
            metadata={"entry_id": entry_id, "error_type": entry.error_type},
        )
    return Response(status_code=204)
