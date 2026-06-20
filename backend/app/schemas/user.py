"""Pydantic schemas for user profile responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    profile_picture_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
