"""User API routes: profile retrieval, name update, avatar management, and password change."""

import filetype
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import DeleteAccountRequest, PasswordChangeRequest, UserResponse, UserUpdate
from app.services import auth_service, user_service

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


def _validate_avatar_magic_bytes(file_data: bytes, declared_content_type: str) -> None:
    """
    Verify the file's magic bytes match the declared MIME type.

    Raises HTTPException 400 if the content cannot be identified or doesn't match.
    This prevents uploads where the extension/Content-Type was spoofed.
    """
    kind = filetype.guess(file_data)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot identify image content. Upload a valid JPEG, PNG, or WebP file.",
        )
    if kind.mime not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content ({kind.mime}) is not a supported image format.",
        )
    if kind.mime != declared_content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File content ({kind.mime}) does not match the declared type "
                f"({declared_content_type}). Upload an unmodified image file."
            ),
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


@router.patch(
    "/me/password",
    response_model=MessageResponse,
    summary="Change the current user's password",
)
async def change_password(
    body: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Verify the current password then update to the new password.

    New password must meet strength requirements (8+ chars, uppercase, lowercase, digit).
    Returns 400 if current_password is wrong or new passwords don't match.
    """
    if not auth_service.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    hashed = auth_service.hash_password(body.new_password)
    await user_service.update_user_password(db, current_user, hashed_password=hashed)
    return MessageResponse(message="Password changed successfully")


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

    Magic bytes are verified against the declared Content-Type to prevent spoofed uploads.
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

    _validate_avatar_magic_bytes(data, file.content_type or "image/jpeg")

    updated = await user_service.update_user_avatar(
        db, current_user.id, data, file.content_type or "image/jpeg"
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_response(updated)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete the current user's account and all their data",
)
async def delete_me(
    body: DeleteAccountRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Hard-delete the authenticated user's account and all associated data
    (chat threads, messages, documents, chunks, refresh tokens).

    Requires the current password to confirm the destructive action.
    Returns 400 if the password is incorrect.
    Auth cookies are cleared in the response so the browser session ends immediately.
    """
    if not auth_service.verify_password(body.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
    user_id = current_user.id
    await user_service.delete_user(db, user_id)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


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
