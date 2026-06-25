"""Authentication service — password hashing, JWT creation/validation, reset token generation,
and refresh token DB storage/revocation."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt as _jwt
import sqlalchemy as sa
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.refresh_token import RefreshToken

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plaintext password matches the stored hash."""
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """Create a short-lived JWT access token for the given subject (user ID string)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return _jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token for the given subject (user ID string)."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return _jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str) -> str:
    """
    Decode and validate a JWT.

    Args:
        token: The encoded JWT string.
        expected_type: Either "access" or "refresh" — prevents cross-token misuse.

    Returns:
        The subject claim (user ID as a string).

    Raises:
        ValueError: If the token is invalid, expired, or the wrong type.
    """
    try:
        payload = _jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except _jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    if payload.get("type") != expected_type:
        raise ValueError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")

    sub: str | None = payload.get("sub")
    if not sub:
        raise ValueError("Token is missing subject claim")

    return sub


def generate_reset_token() -> str:
    """Generate a cryptographically secure URL-safe reset token."""
    return secrets.token_urlsafe(32)


def reset_token_expiry() -> datetime:
    """Return a timestamp 1 hour from now (UTC) for use as a reset token expiry."""
    return datetime.now(timezone.utc) + timedelta(hours=1)


# ── Refresh token DB operations ───────────────────────────────────────────────


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token string. Tokens are never stored in plain text."""
    return hashlib.sha256(token.encode()).hexdigest()


async def store_refresh_token(db: AsyncSession, user_id: UUID, token: str) -> None:
    """
    Persist a new refresh token (hashed) with its expiry.

    Called on login, signup, and token rotation so every active session
    is tracked in the DB and can be individually revoked.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
    )
    db.add(rt)
    await db.commit()


async def get_valid_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    """
    Return the DB record for a refresh token if it exists, is not revoked, and is not expired.

    Returns None if any condition fails — caller should treat this as an invalid token.
    """
    result = await db.execute(
        sa.select(RefreshToken).where(
            RefreshToken.token_hash == _hash_token(token),
            RefreshToken.revoked == sa.false(),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    """
    Mark a refresh token as revoked in the DB.

    Called on logout and on token rotation (after issuing a replacement token).
    Silently does nothing if the token doesn't exist — safe to call unconditionally.
    """
    await db.execute(
        sa.update(RefreshToken)
        .where(RefreshToken.token_hash == _hash_token(token))
        .values(revoked=True)
    )
    await db.commit()


async def revoke_all_user_tokens(db: AsyncSession, user_id: UUID) -> None:
    """
    Revoke all active refresh tokens for a user.

    Called after a successful password reset so any sessions that existed
    before the reset (including an attacker's compromised session) are
    immediately invalidated.
    """
    await db.execute(
        sa.update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked == sa.false())
        .values(revoked=True)
    )
    await db.commit()
