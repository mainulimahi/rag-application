"""SQLAlchemy ORM model for the refresh_tokens table."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        sa.UUID,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        sa.String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
