"""SQLAlchemy ORM model for the documents table.

document_chunks is not mapped here because its `embedding` column uses the pgvector
`vector(768)` type which requires raw SQL for insert/query. All chunk operations in
document_service use sa.text() directly against that table.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
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
