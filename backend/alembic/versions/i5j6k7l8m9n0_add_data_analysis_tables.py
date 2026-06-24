"""Add data_sources, data_files, and data_file_schemas tables for v2 data analysis.

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa

revision = "i5j6k7l8m9n0"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── data_sources ───────────────────────────────────────────────────────────
    # Stores user-configured external data connections (databases, blob storage, APIs).
    # connection_config is JSON encrypted with Fernet before storage.
    op.create_table(
        "data_sources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("connection_config", sa.Text(), nullable=False),
        sa.Column("schema_cache", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(10), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('s3','gcs','azure_blob','postgresql','mysql','sqlite','api')",
            name="ck_data_sources_source_type",
        ),
        sa.CheckConstraint(
            "last_test_status IS NULL OR last_test_status IN ('ok','error')",
            name="ck_data_sources_last_test_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_sources_user_id", "data_sources", ["user_id"])

    # ── data_files ─────────────────────────────────────────────────────────────
    # Uploaded flat files (CSV, Parquet, Excel, JSON) stored in Postgres as bytea,
    # same pattern as the existing documents table.
    op.create_table(
        "data_files",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'processing'")),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('processing','ready','failed')",
            name="ck_data_files_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_files_user_id", "data_files", ["user_id"])

    # ── data_file_schemas ──────────────────────────────────────────────────────
    # One row per column, populated by the DuckDB introspection step after upload.
    op.create_table(
        "data_file_schemas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("data_file_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("column_name", sa.String(255), nullable=False),
        sa.Column("column_type", sa.String(100), nullable=False),
        sa.Column("sample_values", sa.Text(), nullable=True),
        sa.Column("null_count", sa.BigInteger(), nullable=True),
        sa.Column("unique_count", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["data_file_id"], ["data_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_file_schemas_data_file_id", "data_file_schemas", ["data_file_id"])
    op.create_index("ix_data_file_schemas_user_id", "data_file_schemas", ["user_id"])


def downgrade() -> None:
    op.drop_table("data_file_schemas")
    op.drop_table("data_files")
    op.drop_table("data_sources")
