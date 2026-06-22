"""add avatar to users

Revision ID: d8e9f0a1b2c3
Revises: c7a8f9b0e1d2
Create Date: 2026-06-22

Stores profile picture binary data alongside its MIME type directly in the
users table so no external file storage is required.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7a8f9b0e1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_picture_data", sa.LargeBinary(), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile_picture_content_type", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "profile_picture_content_type")
    op.drop_column("users", "profile_picture_data")
