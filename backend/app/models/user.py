"""SQLAlchemy ORM model for the users table."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
