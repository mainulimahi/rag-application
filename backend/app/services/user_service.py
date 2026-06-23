"""User service — database operations for user accounts."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the user with the given email, or None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Return the user with the given ID, or None if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_reset_token(db: AsyncSession, token: str) -> User | None:
    """Return the user with the given reset token, or None if not found."""
    result = await db.execute(select(User).where(User.reset_token == token))
    return result.scalar_one_or_none()


async def get_user_by_verification_token(db: AsyncSession, token: str) -> User | None:
    """Return the user with the given email verification token, or None if not found."""
    result = await db.execute(select(User).where(User.email_verification_token == token))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    name: str,
    email: str,
    hashed_password: str,
) -> User:
    """Insert a new user row and return the persisted User instance."""
    user = User(name=name, email=email, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_reset_token(
    db: AsyncSession,
    user: User,
    token: str | None,
    expires_at: datetime | None,
) -> User:
    """Set or clear the user's password reset token and its expiry."""
    user.reset_token = token
    user.reset_token_expires_at = expires_at
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_name(
    db: AsyncSession, user_id: UUID, name: str
) -> User | None:
    """Update the display name for the given user. Returns None if the user is not found."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.name = name
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_avatar(
    db: AsyncSession, user_id: UUID, data: bytes, content_type: str
) -> User | None:
    """Store a new profile picture (raw bytes + MIME type). Returns None if user not found."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None
    user.profile_picture_data = data
    user.profile_picture_content_type = content_type
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_password(
    db: AsyncSession,
    user: User,
    hashed_password: str,
) -> User:
    """Update the user's hashed password and clear any existing reset token."""
    user.hashed_password = hashed_password
    user.reset_token = None
    user.reset_token_expires_at = None
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def set_verification_token(
    db: AsyncSession, user: User, token: str
) -> User:
    """Store a fresh email verification token (expires in 24 hours)."""
    user.email_verification_token = token
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def mark_user_verified(db: AsyncSession, user: User) -> User:
    """Mark the user's email as verified and clear the verification token."""
    user.is_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: UUID) -> None:
    """
    Hard-delete a user and all their data in FK-safe order.

    Explicit order: refresh_tokens → document_chunks → documents →
    chat_messages → chat_threads → user.
    This avoids relying on DB-level cascades (which may not be set on all tables).
    """
    from app.models.refresh_token import RefreshToken
    from app.models.document import Document, DocumentChunk
    from app.models.chat import ChatMessage, ChatThread

    await db.execute(sa.delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.execute(sa.delete(DocumentChunk).where(DocumentChunk.user_id == user_id))
    await db.execute(sa.delete(Document).where(Document.user_id == user_id))
    await db.execute(sa.delete(ChatMessage).where(ChatMessage.user_id == user_id))
    await db.execute(sa.delete(ChatThread).where(ChatThread.user_id == user_id))
    await db.execute(sa.delete(User).where(User.id == user_id))
    await db.commit()
