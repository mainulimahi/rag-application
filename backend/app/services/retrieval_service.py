"""
Retrieval service — pgvector similarity search scoped to the authenticated user.

All queries filter by user_id; cross-user data access is structurally impossible.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


async def count_ready_documents(db: AsyncSession, user_id: UUID) -> int:
    """Return the count of documents with status='ready' for the user."""
    result = await db.execute(
        sa.select(sa.func.count())
        .select_from(Document)
        .where(
            Document.user_id == user_id,
            Document.status == "ready",
        )
    )
    return result.scalar_one()


async def has_ready_documents(db: AsyncSession, user_id: UUID) -> bool:
    """Return True if the user has at least one document with status='ready'."""
    return await count_ready_documents(db, user_id) > 0


async def similarity_search(
    db: AsyncSession,
    user_id: UUID,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Run a pgvector cosine-similarity search over the user's document chunks.

    Always scoped to user_id — never a global search across all users' embeddings.
    Returns top_k chunks ordered by relevance (lowest cosine distance first).

    Each result: {"text": str, "filename": str, "distance": float}
    """
    distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")

    result = await db.execute(
        sa.select(
            DocumentChunk.chunk_text,
            Document.filename,
            distance_expr,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.user_id == user_id,
            Document.status == "ready",
        )
        .order_by(distance_expr)
        .limit(top_k)
    )

    rows = result.fetchall()
    return [
        {
            "text": row.chunk_text,
            "filename": row.filename,
            "distance": float(row.distance),
        }
        for row in rows
    ]
