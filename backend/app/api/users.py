"""User API routes: profile retrieval, name update, and avatar management."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])

_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


def _build_response(user: User) -> UserResponse:
    """Construct a UserResponse, setting profile_picture_url based on stored data."""
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,  # type: ignore[arg-type]
        profile_picture_url="/api/users/me/avatar" if user.profile_picture_data else None,
        created_at=user.created_at,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current user's profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile. profile_picture_url is set when an avatar exists."""
    return _build_response(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's display name",
)
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update the authenticated user's name. Email is not editable."""
    updated = await user_service.update_user_name(db, current_user.id, body.name)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_response(updated)


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="Upload a profile picture",
)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Accept a JPEG, PNG, or WebP image (max 5 MB) and store it in the users table.
    Returns the updated user profile with profile_picture_url set.
    """
    if file.content_type not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are accepted",
        )
    data = await file.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be 5 MB or smaller",
        )
    updated = await user_service.update_user_avatar(
        db, current_user.id, data, file.content_type or "image/jpeg"
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_response(updated)


@router.get(
    "/me/avatar",
    summary="Serve the current user's profile picture",
    response_class=Response,
)
async def get_avatar(current_user: User = Depends(get_current_user)) -> Response:
    """Return the stored avatar binary with its original Content-Type. 404 if no avatar is set."""
    if not current_user.profile_picture_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No avatar set")
    return Response(
        content=current_user.profile_picture_data,
        media_type=current_user.profile_picture_content_type or "image/jpeg",
    )
