"""Pydantic schemas for user profile responses and updates."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


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
