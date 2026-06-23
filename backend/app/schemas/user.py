"""Pydantic schemas for user profile responses and updates."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.validators import validate_password_strength


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    profile_picture_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Request body for PATCH /api/users/me — only name is editable."""

    name: str = Field(min_length=1, max_length=255)


class PasswordChangeRequest(BaseModel):
    """Request body for PATCH /api/users/me/password."""

    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self


class MessageResponse(BaseModel):
    message: str


class DeleteAccountRequest(BaseModel):
    """Request body for DELETE /api/users/me — password required for confirmation."""

    password: str
