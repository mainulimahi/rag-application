"""SQLAlchemy ORM model for the users table."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.data_source import DataSource
    from app.models.data_file import DataFile


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    profile_picture_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    profile_picture_data: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    profile_picture_content_type: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    reset_token: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    is_verified: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    email_verification_token: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )

    data_sources: Mapped[list[DataSource]] = relationship(
        "DataSource", back_populates="user", cascade="all, delete-orphan"
    )
    data_files: Mapped[list[DataFile]] = relationship(
        "DataFile", back_populates="user", cascade="all, delete-orphan"
    )
