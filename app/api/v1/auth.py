"""app/api/v1/auth.py — Auth router. HTTP only. No business logic."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.dependencies.auth import CurrentUser, get_current_user
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=uuid.uuid4(),
        org_id=body.org_id,
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole.ENGINEER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    user = (await db.execute(select(User).where(User.email == body.email, User.is_active.is_(True)))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    jti = uuid.uuid4().hex
    user.refresh_jti = jti
    await db.commit()

    access = create_access_token(user.id, user.org_id, user.role)
    refresh = create_refresh_token(user.id, jti)
    from app.core.config import settings
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        payload = decode_refresh_token(body.refresh_token)
        user_id = uuid.UUID(payload["sub"])
        jti = payload["jti"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = (await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))).scalar_one_or_none()
    if not user or user.refresh_jti != jti:
        raise HTTPException(status_code=401, detail="Token revoked")

    new_jti = uuid.uuid4().hex
    user.refresh_jti = new_jti
    await db.commit()

    from app.core.config import settings
    access = create_access_token(user.id, user.org_id, user.role)
    refresh_token = create_refresh_token(user.id, new_jti)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == current_user.id))).scalar_one_or_none()
    if user:
        user.refresh_jti = None
        await db.commit()


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    return current_user.__dict__
