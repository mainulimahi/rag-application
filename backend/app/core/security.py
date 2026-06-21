"""FastAPI security dependency — validates JWTs from httpOnly cookie or Authorization header."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services import auth_service, user_service

# auto_error=False so we can fall back to cookie auth when no Authorization header is present
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that validates the JWT and returns the authenticated user.

    Prefers the Authorization: Bearer header (for API clients / curl).
    Falls back to the access_token httpOnly cookie (set by login/signup for browser clients).

    Raises HTTP 401 if the token is missing, invalid, expired, or the user no longer exists.
    """
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token: Optional[str] = None
    if credentials:
        token = credentials.credentials
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise invalid

    try:
        user_id_str = auth_service.decode_token(token, expected_type="access")
        user_id = UUID(user_id_str)
    except (ValueError, Exception):
        raise invalid

    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise invalid
    return user
