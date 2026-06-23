"""Add email verification to users; soft delete to chat_threads and documents.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users: email verification fields ──────────────────────────────────────
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("email_verification_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True))

    # ── chat_threads: soft delete ─────────────────────────────────────────────
    op.add_column("chat_threads", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # ── documents: soft delete ────────────────────────────────────────────────
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "deleted_at")
    op.drop_column("chat_threads", "deleted_at")
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "is_verified")
