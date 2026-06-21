"""add processing status fields to documents

Revision ID: 717d7488b704
Revises: 0001
Create Date: 2026-06-21 19:56:35.872206

Autogenerate note: The raw output also wanted to drop document_chunks (unmapped —
its `vector` column is pgvector-only and can't be described by SQLAlchemy ORM) and
several FK constraints that were created with raw SQL in migration 0001.
All such destructive statements have been removed; only the new columns are added.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "717d7488b704"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="processing",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('processing', 'ready', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "status")
