"""
Document service — upload validation, text extraction, chunking, embedding, and CRUD.

All operations that access user data are scoped to a user_id — this is the
multi-tenancy security boundary (same pattern as chat_service).

Processing flow:
  1. validate_file()          — raise ValueError on bad type/size before touching the DB
  2. save_document()          — persist the raw file with status='processing'
  3. process_document()       — extract → chunk → embed → save chunks, then mark ready/failed
     Called as a FastAPI BackgroundTask so the upload endpoint responds immediately.
"""

from __future__ import annotations

import io
import logging
from uuid import UUID

import sqlalchemy as sa
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.embedding_service import get_embedding_provider

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# ~500 tokens per chunk with ~100 token overlap (4 chars ≈ 1 token heuristic).
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=400,
    length_function=len,
)

# Embed at most this many chunks per API call to stay under Gemini batch limits.
_EMBED_BATCH_SIZE = 20


# ── Validation ─────────────────────────────────────────────────────────────────


def validate_file(filename: str, content_type: str, file_size: int) -> None:
    """
    Raise ValueError with a user-facing message if the file is invalid.

    Checks extension, MIME type, and file size — in that order so the most
    specific error is returned first.
    """
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {allowed}")

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Unsupported content type '{content_type}'. Upload PDF, DOCX, TXT, or MD files."
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        mb = file_size / (1024 * 1024)
        raise ValueError(f"File too large ({mb:.1f} MB). Maximum allowed size is 20 MB.")


# ── Text extraction ────────────────────────────────────────────────────────────


def extract_text(file_data: bytes, filename: str, content_type: str) -> str:
    """
    Extract plain text from an uploaded file.

    Dispatches by content type (with filename extension as fallback).
    Raises ValueError with a descriptive message on extraction failure.
    """
    is_pdf = (
        content_type == "application/pdf"
        or filename.lower().endswith(".pdf")
    )
    is_docx = (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or filename.lower().endswith(".docx")
    )

    if is_pdf:
        return _extract_pdf(file_data)
    if is_docx:
        return _extract_docx(file_data)

    # TXT / MD — try UTF-8 then fall back to latin-1 for Windows-authored files.
    try:
        return file_data.decode("utf-8")
    except UnicodeDecodeError:
        return file_data.decode("latin-1")


def _extract_pdf(file_data: bytes) -> str:
    try:
        import pypdf  # lazy import — only needed for PDF files

        reader = pypdf.PdfReader(io.BytesIO(file_data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(p for p in pages if p.strip()).strip()
        if not text:
            raise ValueError(
                "PDF contains no extractable text. It may be image-only or scanned."
            )
        return text
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"PDF extraction failed: {exc}") from exc


def _extract_docx(file_data: bytes) -> str:
    try:
        import docx  # lazy import — only needed for DOCX files (installed as python-docx)

        doc = docx.Document(io.BytesIO(file_data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()
        if not text:
            raise ValueError("DOCX contains no extractable text.")
        return text
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"DOCX extraction failed: {exc}") from exc


# ── Chunking ───────────────────────────────────────────────────────────────────


def chunk_text(text: str) -> list[str]:
    """Split extracted text into overlapping chunks for embedding."""
    return _splitter.split_text(text)


# ── DB operations ──────────────────────────────────────────────────────────────


async def save_document(
    db: AsyncSession,
    user_id: UUID,
    filename: str,
    content_type: str,
    file_data: bytes,
) -> Document:
    """
    Persist the raw document file with status='processing'.

    Chunks are not stored here — they are added by process_document() once
    extraction and embedding have succeeded.
    """
    doc = Document(
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        file_data=file_data,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def process_document(
    document_id: UUID,
    user_id: UUID,
    file_data: bytes,
    filename: str,
    content_type: str,
) -> None:
    """
    Background processing step: extract → chunk → embed → store → mark ready.

    Creates its own DB session because this runs after the HTTP response has
    been sent and the request-scoped session is already closed.
    On any failure the document is marked 'failed' with the error message.
    """
    from app.db.session import AsyncSessionLocal  # local import avoids circular dep at module load

    async with AsyncSessionLocal() as db:
        try:
            text = extract_text(file_data, filename, content_type)
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("No text chunks could be produced from this document.")

            await _save_chunks_with_embeddings(db, document_id, user_id, chunks)
            await _mark_ready(db, document_id)
            logger.info("Document %s processed: %d chunks", document_id, len(chunks))

        except Exception as exc:
            logger.error("Document %s processing failed: %s", document_id, exc)
            try:
                async with AsyncSessionLocal() as err_db:
                    await _mark_failed(err_db, document_id, str(exc))
            except Exception:
                logger.exception("Could not write failure status for document %s", document_id)


async def _save_chunks_with_embeddings(
    db: AsyncSession,
    document_id: UUID,
    user_id: UUID,
    chunks: list[str],
) -> None:
    """
    Embed all chunks in batches and insert them into document_chunks.

    Uses raw SQL with ::vector cast because SQLAlchemy has no native understanding
    of the pgvector `vector` type.
    """
    embedding_provider = get_embedding_provider()

    for batch_start in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
        vectors = await embedding_provider.embed_texts(batch)

        for offset, (chunk_text, vector) in enumerate(zip(batch, vectors)):
            chunk_index = batch_start + offset
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            await db.execute(
                sa.text(
                    """
                    INSERT INTO document_chunks
                        (document_id, user_id, chunk_text, embedding, chunk_index)
                    VALUES
                        (:document_id, :user_id, :chunk_text, :embedding::vector, :chunk_index)
                    """
                ),
                {
                    "document_id": str(document_id),
                    "user_id": str(user_id),
                    "chunk_text": chunk_text,
                    "embedding": vector_str,
                    "chunk_index": chunk_index,
                },
            )

    await db.commit()


async def _mark_ready(db: AsyncSession, document_id: UUID) -> None:
    """Set document.status = 'ready' after successful processing."""
    await db.execute(
        sa.update(Document).where(Document.id == document_id).values(status="ready")
    )
    await db.commit()


async def _mark_failed(db: AsyncSession, document_id: UUID, error: str) -> None:
    """Set document.status = 'failed' and store the error message (truncated to 1 KB)."""
    await db.execute(
        sa.update(Document)
        .where(Document.id == document_id)
        .values(status="failed", processing_error=error[:1000])
    )
    await db.commit()


# ── Query operations ───────────────────────────────────────────────────────────


async def list_documents(db: AsyncSession, user_id: UUID) -> list[dict]:
    """
    Return all documents for a user with their chunk counts, newest first.

    Returns dicts with: id, filename, content_type, status, processing_error,
    chunk_count, uploaded_at — never includes file_data (raw bytes).
    """
    result = await db.execute(
        sa.text(
            """
            SELECT
                d.id,
                d.filename,
                d.content_type,
                d.status,
                d.processing_error,
                d.uploaded_at,
                COUNT(c.id)::int AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks c
                ON c.document_id = d.id AND c.user_id = d.user_id
            WHERE d.user_id = :user_id
            GROUP BY d.id
            ORDER BY d.uploaded_at DESC
            """
        ),
        {"user_id": str(user_id)},
    )
    return [dict(row._mapping) for row in result.all()]


async def get_document(
    db: AsyncSession, document_id: UUID, user_id: UUID
) -> Document | None:
    """Return a document only if it exists and belongs to user_id."""
    result = await db.execute(
        sa.select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_document_status(
    db: AsyncSession, document_id: UUID, user_id: UUID
) -> dict | None:
    """
    Return status info for a single document.

    Returns None if the document doesn't exist or isn't owned by user_id.
    """
    result = await db.execute(
        sa.text(
            """
            SELECT
                d.id,
                d.status,
                d.processing_error,
                COUNT(c.id)::int AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks c
                ON c.document_id = d.id AND c.user_id = d.user_id
            WHERE d.id = :document_id AND d.user_id = :user_id
            GROUP BY d.id
            """
        ),
        {"document_id": str(document_id), "user_id": str(user_id)},
    )
    row = result.one_or_none()
    return dict(row._mapping) if row is not None else None


async def delete_document(
    db: AsyncSession, document_id: UUID, user_id: UUID
) -> bool:
    """
    Delete a document and cascade-delete its chunks (via DB ON DELETE CASCADE).

    Returns False if the document doesn't exist or isn't owned by user_id.
    """
    doc = await get_document(db, document_id, user_id)
    if doc is None:
        return False
    await db.delete(doc)
    await db.commit()
    return True
