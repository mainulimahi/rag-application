"""Pydantic schemas for authentication request and response bodies."""

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.core.validators import validate_password_strength
from app.schemas.user import UserResponse


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce uppercase, lowercase, digit, and 8-char minimum."""
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "SignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce same strength rules as signup."""
        return validate_password_strength(v)


class MessageResponse(BaseModel):
    message: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
