"""Authentication API routes: signup, login, token refresh, logout, forgot-password,
reset-password, verify-email, resend-verification."""

import logging
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.schemas.user import UserResponse
from app.services import auth_service, email_service, user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


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
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit("3/minute")
async def signup(
    request: Request,
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a new user account and either verify it immediately or send a verification email.

    When REQUIRE_EMAIL_VERIFICATION=false (local dev): marks the account verified immediately
    and returns a plain success message — user can log in right away with any email address.
    When REQUIRE_EMAIL_VERIFICATION=true (production): sends a verification email and the user
    must click the link before logging in.
    Returns 409 if the email is already registered.
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

    if not settings.REQUIRE_EMAIL_VERIFICATION:
        await user_service.mark_user_verified(db, user)
        logger.info("New user registered (auto-verified, verification disabled): %s", user.email)
        return {"message": "Account created successfully. You can now sign in."}

    token = secrets.token_urlsafe(32)
    await user_service.set_verification_token(db, user, token)

    try:
        await email_service.send_verification_email(str(body.email), body.name, token)
    except Exception:
        # Email failure is logged in the service — don't fail the signup.
        pass

    logger.info("New user registered (unverified): %s", user.email)

    response: dict = {"message": "Please check your email to verify your account"}
    if settings.ENVIRONMENT == "local":
        response["debug_verification_link"] = f"http://localhost:3000/verify-email?token={token}"
    return response


@router.post(
    "/verify-email",
    response_model=UserResponse,
    summary="Verify email address using the token from the verification email",
)
async def verify_email(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Validate the email verification token, mark the account as verified,
    and set auth cookies so the user is logged in immediately.

    Returns 400 if the token is invalid or expired.
    """
    user = await user_service.get_user_by_verification_token(db, token)
    if not user or not user.email_verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )
    if datetime.now(timezone.utc) > user.email_verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link has expired. Request a new one.",
        )

    await user_service.mark_user_verified(db, user)

    access_token = auth_service.create_access_token(str(user.id))
    refresh_token = auth_service.create_refresh_token(str(user.id))
    await auth_service.store_refresh_token(db, user.id, refresh_token)
    _set_auth_cookies(response, access_token, refresh_token)

    logger.info("Email verified for user: %s", user.email)
    return UserResponse.model_validate(user)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend the email verification link",
)
@limiter.limit("2/hour")
async def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Generate a fresh verification token and resend the verification email.

    Always returns the same response regardless of whether the email exists or is
    already verified — prevents email enumeration. Rate-limited to 2 requests/hour.
    """
    generic = MessageResponse(
        message="If that email has an unverified account, a new verification link has been sent."
    )

    user = await user_service.get_user_by_email(db, body.email)
    if not user or user.is_verified:
        return generic

    token = secrets.token_urlsafe(32)
    await user_service.set_verification_token(db, user, token)
    try:
        await email_service.send_verification_email(str(body.email), user.name, token)
    except Exception:
        pass

    return generic


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Authenticate with email and password",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Validate email/password credentials and set JWT access + refresh token cookies.

    Returns 401 if the credentials are incorrect.
    Returns 403 if the account email has not been verified yet.
    """
    user = await user_service.get_user_by_email(db, body.email)
    if not user or not auth_service.verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Please verify your email before logging in. "
                "Check your inbox or request a new verification link."
            ),
        )

    access_token = auth_service.create_access_token(str(user.id))
    refresh_token = auth_service.create_refresh_token(str(user.id))
    await auth_service.store_refresh_token(db, user.id, refresh_token)

    _set_auth_cookies(response, access_token, refresh_token)
    logger.info("User logged in: %s", user.email)
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
    Read the refresh_token cookie, validate it (JWT + DB record), revoke the old token,
    and issue a new rotated token pair as cookies.

    Returns 401 if the cookie is missing, JWT is invalid/expired, or the token has been
    revoked in the DB (e.g. after logout on another device).
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

    db_token = await auth_service.get_valid_refresh_token(db, refresh_token)
    if db_token is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    await auth_service.revoke_refresh_token(db, refresh_token)
    new_access = auth_service.create_access_token(str(user.id))
    new_refresh = auth_service.create_refresh_token(str(user.id))
    await auth_service.store_refresh_token(db, user.id, new_refresh)

    _set_auth_cookies(response, new_access, new_refresh)
    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out the current user",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Revoke the current refresh token in the DB and expire both auth cookies.

    No auth required — always returns 200 so the frontend can call unconditionally.
    """
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            await auth_service.revoke_refresh_token(db, refresh_token)
        except Exception:
            pass
    _clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully")


@router.post(
    "/forgot-password",
    response_model=dict,
    summary="Request a password reset link",
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a password reset token and send it to the user via email.

    Always returns the same message regardless of whether the email exists (prevents
    enumeration). In local/dev mode, also returns debug_reset_link in the response body.
    """
    generic_response: dict = {
        "message": "If that email is registered, a password reset link has been sent."
    }

    user = await user_service.get_user_by_email(db, body.email)
    if not user:
        return generic_response

    token = auth_service.generate_reset_token()
    expires_at = auth_service.reset_token_expiry()
    await user_service.update_user_reset_token(db, user, token=token, expires_at=expires_at)

    reset_link = f"http://localhost:3000/reset-password?token={token}"

    try:
        await email_service.send_password_reset_email(str(body.email), user.name, token)
    except Exception:
        logger.warning("Email send failed for %s — debug_reset_link still included in local", body.email)

    if settings.ENVIRONMENT == "local":
        return {**generic_response, "debug_reset_link": reset_link}
    return generic_response


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a valid reset token",
)
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Validate the reset token and update the user's password.

    Password must meet strength requirements (8+ chars, uppercase, lowercase, digit).
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
    logger.info("Password reset for user: %s", user.email)

    return MessageResponse(message="Password reset successfully. You can now log in.")
