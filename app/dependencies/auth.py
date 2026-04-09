"""
app/dependencies/auth.py
Zero-trust RBAC: explicit dependency on every protected route.
Never trust user-supplied org_id from request payload.
Current user's org_id is always sourced from the validated JWT.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole


@dataclass
class CurrentUser:
    id: uuid.UUID
    org_id: uuid.UUID
    role: str
    email: str


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    Decode and validate JWT. Fetch user from DB to verify is_active.
    Raises 401 on any failure — no leaking of reason why.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_exc

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org_id"])
        role = payload["role"]
    except (JWTError, KeyError, ValueError):
        raise credentials_exc

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exc

    return CurrentUser(id=user.id, org_id=user.org_id, role=user.role, email=user.email)


def require_role(*roles: UserRole):
    """
    Dependency factory: restrict endpoint to listed roles.
    Used as: Depends(require_role(UserRole.SRE, UserRole.ADMIN))
    """
    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# Pre-built dependencies for common role combos
RequireEngineer = Depends(require_role(UserRole.ENGINEER, UserRole.SRE, UserRole.ADMIN, UserRole.CI_AGENT))
RequireSRE = Depends(require_role(UserRole.SRE, UserRole.ADMIN))
RequireAdmin = Depends(require_role(UserRole.ADMIN))
