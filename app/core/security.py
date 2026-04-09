"""
app/core/security.py
Password hashing (Argon2id) and JWT access/refresh token management.
Never store plaintext passwords. Never log tokens.
"""
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against Argon2id hash."""
    return pwd_context.verify(plain, hashed)


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + expires_delta
    payload["iat"] = datetime.now(UTC)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID, org_id: UUID, role: str) -> str:
    """Create short-lived JWT access token (15 min)."""
    return _create_token(
        data={"sub": str(user_id), "org_id": str(org_id), "role": role, "type": "access"},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: UUID, jti: str) -> str:
    """Create long-lived JWT refresh token (7 days). jti tracked in Redis/DB for revocation."""
    return _create_token(
        data={"sub": str(user_id), "jti": jti, "type": "refresh"},
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate access token.
    Raises JWTError on invalid/expired token.
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode and validate refresh token. Caller must verify jti not revoked."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    return payload
