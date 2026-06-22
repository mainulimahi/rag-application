"""SQLAlchemy ORM models for chat_threads and chat_messages tables."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    thread_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    sources: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
