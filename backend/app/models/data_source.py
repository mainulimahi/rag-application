"""SQLAlchemy ORM model for data_sources (v2 data analysis)."""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[UUID] = mapped_column(
        sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(sa.UUID, nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    connection_config: Mapped[str] = mapped_column(sa.Text, nullable=False)
    schema_cache: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_test_status: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False
    )
