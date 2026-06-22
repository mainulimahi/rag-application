"""add sources to chat_messages

Revision ID: c7a8f9b0e1d2
Revises: 717d7488b704
Create Date: 2026-06-22

Stores which tools the RAG agent used to generate each assistant reply:
'llm_only', 'retrieval', 'web_search', or 'both'. NULL for user messages.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a8f9b0e1d2"
down_revision: Union[str, None] = "717d7488b704"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("sources", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "sources")
