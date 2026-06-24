"""SQLAlchemy ORM models for data_files and data_file_schemas (v2 data analysis)."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataFile(Base):
    __tablename__ = "data_files"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    file_data: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    file_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default=sa.text("'processing'")
    )
    processing_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    row_count: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )


class DataFileSchema(Base):
    __tablename__ = "data_file_schemas"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    data_file_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    column_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    column_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    sample_values: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    null_count: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    unique_count: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
