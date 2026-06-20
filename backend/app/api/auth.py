"""Authentication API routes: signup, login, token refresh, forgot-password, reset-password."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.schemas.user import UserResponse
from app.services import auth_service, user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """
    Create a new user account, hash the password, and return JWT access + refresh tokens.

    Returns 409 if the email is already registered.
    """
    existing = await user_service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    hashed = auth_service.hash_password(body.password)
    user = await user_service.create_user(db, name=body.name, email=body.email, hashed_password=hashed)

    return AuthResponse(
        access_token=auth_service.create_access_token(str(user.id)),
        refresh_token=auth_service.create_refresh_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate with email and password",
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """
    Validate email/password credentials and return JWT access + refresh tokens.

    Returns 401 if the credentials are incorrect (intentionally vague to prevent enumeration).
    """
    user = await user_service.get_user_by_email(db, body.email)
    if not user or not auth_service.verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    return AuthResponse(
        access_token=auth_service.create_access_token(str(user.id)),
        refresh_token=auth_service.create_refresh_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange a refresh token for new access and refresh tokens",
)
async def refresh_tokens(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """
    Validate the refresh token and issue a new access + refresh token pair (token rotation).

    Returns 401 if the refresh token is invalid or expired.
    """
    try:
        user_id_str = auth_service.decode_token(body.refresh_token, expected_type="refresh")
        user = await user_service.get_user_by_id(db, UUID(user_id_str))
    except (ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return AuthResponse(
        access_token=auth_service.create_access_token(str(user.id)),
        refresh_token=auth_service.create_refresh_token(str(user.id)),
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/forgot-password",
    response_model=dict,
    summary="Request a password reset link",
)
async def forgot_password(
    body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Generate a password reset token for the given email.

    Always returns the same message regardless of whether the email exists (prevents enumeration).
    STUB: no email is sent — the reset link is logged and returned in debug_reset_link for development.
    """
    generic_response = {
        "message": "If that email is registered, a password reset link has been sent."
    }

    user = await user_service.get_user_by_email(db, body.email)
    if not user:
        return generic_response

    token = auth_service.generate_reset_token()
    expires_at = auth_service.reset_token_expiry()
    await user_service.update_user_reset_token(db, user, token=token, expires_at=expires_at)

    # STUB: in production, send this link via email (SMTP not configured at this stage)
    reset_link = f"http://localhost:3000/reset-password?token={token}"
    print(f"[STUB] Password reset link for {body.email}: {reset_link}")

    return {**generic_response, "debug_reset_link": reset_link}


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a valid reset token",
)
async def reset_password(
    body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Validate the reset token and update the user's password.

    Returns 400 if the token is invalid or expired.
    """
    user = await user_service.get_user_by_reset_token(db, body.token)
    if not user or not user.reset_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if datetime.now(timezone.utc) > user.reset_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    hashed = auth_service.hash_password(body.new_password)
    await user_service.update_user_password(db, user, hashed_password=hashed)

    return MessageResponse(message="Password reset successfully. You can now log in.")
