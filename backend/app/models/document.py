"""SQLAlchemy ORM models for documents and document_chunks.

DocumentChunk uses pgvector.sqlalchemy.Vector for the embedding column so
chunk insertion can go through the ORM instead of raw SQL.

Note: document_chunks is still excluded from Alembic autogenerate
(see alembic/env.py _AUTOGENERATE_EXCLUDE_TABLES) because the table was
created via raw SQL in migration 0001 and the Vector type cannot be diffed
reliably by the standard Alembic dialect.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    file_data: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default="processing"
    )
    processing_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    document_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    chunk_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(768), nullable=False)
    chunk_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
