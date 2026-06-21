"""Authentication API routes: signup, login, token refresh, logout, forgot-password, reset-password."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
)
from app.schemas.user import UserResponse
from app.services import auth_service, user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly auth cookies on the response. secure=True in production only."""
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=secure,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        secure=secure,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Expire both auth cookies (used on logout and failed refresh)."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def signup(
    body: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Create a new user account, hash the password, and set JWT access + refresh token cookies.

    Returns 409 if the email is already registered.
    Tokens are returned as httpOnly cookies, not in the response body.
    """
    existing = await user_service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    hashed = auth_service.hash_password(body.password)
    user = await user_service.create_user(
        db, name=body.name, email=body.email, hashed_password=hashed
    )

    _set_auth_cookies(
        response,
        auth_service.create_access_token(str(user.id)),
        auth_service.create_refresh_token(str(user.id)),
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Authenticate with email and password",
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Validate email/password credentials and set JWT access + refresh token cookies.

    Returns 401 if the credentials are incorrect (intentionally vague to prevent enumeration).
    Tokens are returned as httpOnly cookies, not in the response body.
    """
    user = await user_service.get_user_by_email(db, body.email)
    if not user or not auth_service.verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    _set_auth_cookies(
        response,
        auth_service.create_access_token(str(user.id)),
        auth_service.create_refresh_token(str(user.id)),
    )
    return UserResponse.model_validate(user)


@router.post(
    "/refresh",
    response_model=UserResponse,
    summary="Exchange the refresh token cookie for new access and refresh token cookies",
)
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Read the refresh_token cookie, validate it, and issue a rotated token pair as new cookies.

    Returns 401 if the refresh token cookie is missing, invalid, or expired.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )

    try:
        user_id_str = auth_service.decode_token(refresh_token, expected_type="refresh")
        user = await user_service.get_user_by_id(db, UUID(user_id_str))
    except (ValueError, Exception):
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if not user:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    _set_auth_cookies(
        response,
        auth_service.create_access_token(str(user.id)),
        auth_service.create_refresh_token(str(user.id)),
    )
    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out the current user",
)
async def logout(response: Response) -> MessageResponse:
    """
    Expire the access and refresh token cookies.

    No auth required — always returns 200 so the frontend can call this unconditionally.
    """
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully")


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
