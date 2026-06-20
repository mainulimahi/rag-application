"""User service — database operations for user accounts."""

from datetime import datetime, timezone
from uuid import UUID

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
