from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.models.user import UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.rule_repository import RuleRepository

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    condition_yaml: str
    action_type: str
    action_params: dict | None = None
    confidence: float = 1.0


class RuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    condition_yaml: str
    action_type: str
    action_params: dict | None
    confidence: float
    hit_count: int
    success_count: int
    failure_count: int
    is_active: bool
    source: str
    model_config = {"from_attributes": True}


@router.get("", response_model=dict)
async def list_rules(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    active_only: bool = True,
) -> dict:
    repo = RuleRepository(db)
    rules = await repo.list_active(org_id=current_user.org_id, active_only=active_only)
    return {"items": [RuleResponse.model_validate(r) for r in rules], "total": len(rules)}


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    body: RuleCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    if current_user.role not in (UserRole.SRE.value, UserRole.ADMIN.value):
        raise HTTPException(403, "SRE or ADMIN required")
    async with db.begin():
        repo = RuleRepository(db)
        rule = await repo.create(
            org_id=current_user.org_id,
            created_by=current_user.id,
            name=body.name,
            description=body.description,
            condition_yaml=body.condition_yaml,
            action_type=body.action_type,
            action_params=body.action_params,
            confidence=body.confidence,
        )
        await AuditRepository(db).write(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action="RULE_CREATED",
            resource_type="rule",
            resource_id=rule.id,
            metadata={"name": body.name},
        )
    return RuleResponse.model_validate(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Response:
    if current_user.role not in (UserRole.SRE.value, UserRole.ADMIN.value):
        raise HTTPException(403, "SRE or ADMIN required")
    async with db.begin():
        repo = RuleRepository(db)
        rule = await repo.get_by_id(rule_id, org_id=current_user.org_id)
        if not rule:
            raise HTTPException(404, "Rule not found")
        await repo.soft_delete(rule_id)
        await AuditRepository(db).write(
            org_id=current_user.org_id,
            user_id=current_user.id,
            action="RULE_DELETED",
            resource_type="rule",
            resource_id=rule_id,
            metadata={"name": rule.name},
        )
    return Response(status_code=204)
