from __future__ import annotations
import json
import uuid
from typing import Annotated
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.models.user import UserRole
from app.repositories.repair_repository import RepairRepository
from app.schemas.repair import RepairRequest
from app.services.repair_orchestrator import RepairOrchestrator
from app.services.rule_engine import RuleEngineService
from app.services.wiki_service import WikiService

router = APIRouter(prefix="/repairs", tags=["repairs"])
_rule_engine = RuleEngineService()
_wiki = WikiService()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream(repair_id, org_id, user_id, body, db, ip):
    orch = RepairOrchestrator(db, _rule_engine, _wiki)
    async for ev in orch.orchestrate(
        repair_id=repair_id, org_id=org_id, user_id=user_id,
        stack_trace=body.stack_trace, repo_path=body.repo_path,
        validation_level=body.validation_level,
        max_iterations=body.max_iterations, ip_address=ip,
    ):
        yield _sse(ev["event"], ev["data"])
    yield _sse("heartbeat", {"repair_id": str(repair_id), "done": True})


@router.post("")
async def create_repair(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: RepairRequest = Body(...),
) -> StreamingResponse:
    repair_id = uuid.uuid4()
    ip = request.client.host if request.client else None
    return StreamingResponse(
        _stream(repair_id, current_user.org_id, current_user.id, body, db, ip),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("")
async def list_repairs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    limit: int = 20,
) -> dict:
    repo = RepairRepository(db)
    user_filter = current_user.id if current_user.role == UserRole.ENGINEER.value else None
    items, total = await repo.list_for_org(
        org_id=current_user.org_id, user_id=user_filter, page=page, limit=limit,
    )
    return {"items": [i.__dict__ for i in items], "total": total, "page": page, "limit": limit}


@router.get("/{repair_id}")
async def get_repair(
    repair_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    repo = RepairRepository(db)
    session = await repo.get_by_id(repair_id, current_user.org_id)
    if not session:
        raise HTTPException(404, "Not found")
    return session.__dict__
