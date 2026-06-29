"""Data file service — upload validation, background schema extraction, and CRUD.

Upload flow:
  1. validate_data_file()          — raise 422 on bad extension or oversized file
  2. upload_data_file()            — persist raw bytes with status='processing'
  3. _extract_schema_background()  — DuckDB introspection → DataFileSchema rows → status update
     Runs via FastAPI BackgroundTask after the HTTP response is sent.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import filetype

import sqlalchemy as sa
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.data_file import DataFile, DataFileSchema
from app.services import duckdb_service

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = duckdb_service.SUPPORTED_EXTENSIONS
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Filename sanitization ──────────────────────────────────────────────────────


def sanitize_filename(filename: str) -> str:
    """Strip path separators, null bytes, and control characters from a filename."""
    name = re.sub(r"[^\w\-_\. ]", "_", Path(filename).name.strip())
    return name[:255] or "upload"


# ── Validation ─────────────────────────────────────────────────────────────────


def validate_data_file(filename: str, file_size: int) -> None:
    """Raise 422 on unsupported extension or oversized file."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: {allowed}",
        )
    if file_size > MAX_FILE_SIZE:
        mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File too large ({mb:.1f} MB). Maximum allowed size is 20 MB.",
        )


_PARQUET_MAGIC = b"PAR1"

_EXCEL_MIMES = {
    "application/zip",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def validate_data_file_content(filename: str, file_bytes: bytes) -> None:
    """Raise 422 if file magic bytes don't match the declared extension."""
    ext = Path(filename).suffix.lower()

    if ext == ".parquet":
        if not file_bytes[:4] == _PARQUET_MAGIC:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File content does not match the declared file type (expected Parquet)",
            )
    elif ext in (".xlsx", ".xls"):
        kind = filetype.guess(file_bytes)
        if kind is None or kind.mime not in _EXCEL_MIMES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File content does not match the declared file type (expected Excel)",
            )
        # Zip bomb protection for Excel files (ZIP-based).
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 100 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            "File appears to be a zip bomb or is excessively large when "
                            "decompressed. Maximum uncompressed size is 100 MB."
                        ),
                    )
        except zipfile.BadZipFile:
            pass
    elif ext == ".json":
        try:
            json.loads(file_bytes[:1024].decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File content does not match the declared file type (expected JSON)",
            )
    # CSV and TSV have no magic bytes — extension match is sufficient


# ── Upload ─────────────────────────────────────────────────────────────────────


async def upload_data_file(
    db: AsyncSession,
    user_id: UUID,
    filename: str,
    file_bytes: bytes,
    content_type: str,
    background_tasks,
) -> DataFile:
    """
    Validate, persist, and schedule background schema extraction for a data file.

    Returns immediately with status='processing'. Schema extraction runs in the
    background after the response is sent.
    """
    validate_data_file(filename, len(file_bytes))
    validate_data_file_content(filename, file_bytes)
    safe_filename = sanitize_filename(filename)

    data_file = DataFile(
        user_id=user_id,
        filename=safe_filename,
        file_data=file_bytes,
        file_size=len(file_bytes),
        content_type=content_type,
        status="processing",
    )
    db.add(data_file)
    await db.commit()
    await db.refresh(data_file)

    background_tasks.add_task(
        _extract_schema_background,
        data_file_id=data_file.id,
        user_id=user_id,
        file_bytes=file_bytes,
        filename=safe_filename,
    )
    return data_file


async def _extract_schema_background(
    data_file_id: UUID,
    user_id: UUID,
    file_bytes: bytes,
    filename: str,
) -> None:
    """
    Background task: run DuckDB schema extraction and persist the results.

    Creates its own DB session because the request session is already closed.
    The blocking duckdb_service.extract_schema() call is offloaded to the
    default thread-pool executor to avoid blocking the event loop.
    """
    from app.db.session import AsyncSessionLocal

    loop = asyncio.get_running_loop()
    async with AsyncSessionLocal() as db:
        try:
            schema_result = await loop.run_in_executor(
                None,
                lambda: duckdb_service.extract_schema(file_bytes, filename),
            )

            schema_rows = [
                DataFileSchema(
                    data_file_id=data_file_id,
                    user_id=user_id,
                    column_name=str(col["name"]).strip().replace(' ', '_'),
                    column_type=col["type"],
                    sample_values=(
                        json.dumps(col["sample_values"])
                        if col["sample_values"] is not None
                        else None
                    ),
                    null_count=col["null_count"],
                    unique_count=col["unique_count"],
                )
                for col in schema_result["columns"]
            ]
            db.add_all(schema_rows)

            await db.execute(
                sa.update(DataFile)
                .where(DataFile.id == data_file_id)
                .values(status="ready", row_count=schema_result["row_count"])
            )
            await db.commit()
            logger.info(
                "Data file %s ready: %d columns, %d rows",
                data_file_id,
                len(schema_rows),
                schema_result["row_count"],
            )

        except Exception as exc:
            logger.error(
                "Schema extraction failed for data file %s: %s", data_file_id, exc
            )
            try:
                async with AsyncSessionLocal() as err_db:
                    await err_db.execute(
                        sa.update(DataFile)
                        .where(DataFile.id == data_file_id)
                        .values(status="failed", processing_error=str(exc)[:1000])
                    )
                    await err_db.commit()
            except Exception:
                logger.exception(
                    "Could not write failure status for data file %s", data_file_id
                )


# ── CRUD ───────────────────────────────────────────────────────────────────────


async def list_data_files(db: AsyncSession, user_id: UUID) -> list[DataFile]:
    """Return all non-deleted data files with schema_columns loaded, newest first."""
    result = await db.execute(
        sa.select(DataFile)
        .options(selectinload(DataFile.schema_columns))
        .where(DataFile.user_id == user_id, DataFile.deleted_at.is_(None))
        .order_by(DataFile.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def get_data_file(
    db: AsyncSession,
    user_id: UUID,
    data_file_id: UUID,
    load_schema: bool = True,
) -> DataFile:
    """Return a data file only if it belongs to user_id; raise 404 otherwise."""
    query = sa.select(DataFile).where(
        DataFile.id == data_file_id,
        DataFile.user_id == user_id,
        DataFile.deleted_at.is_(None),
    )
    if load_schema:
        query = query.options(selectinload(DataFile.schema_columns))
    result = await db.execute(query)
    data_file = result.scalar_one_or_none()
    if data_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data file not found",
        )
    return data_file


async def get_data_file_status(
    db: AsyncSession, user_id: UUID, data_file_id: UUID
) -> dict:
    """Lightweight status check — avoids loading schema_columns."""
    data_file = await get_data_file(db, user_id, data_file_id, load_schema=False)
    count_result = await db.execute(
        sa.select(sa.func.count())
        .select_from(DataFileSchema)
        .where(DataFileSchema.data_file_id == data_file_id)
    )
    column_count: int = count_result.scalar_one()
    return {
        "id": data_file.id,
        "status": data_file.status,
        "processing_error": data_file.processing_error,
        "row_count": data_file.row_count,
        "column_count": column_count,
    }


async def delete_data_file(
    db: AsyncSession, user_id: UUID, data_file_id: UUID
) -> None:
    """Soft-delete the data file; hard-delete its schema rows immediately."""
    data_file = await get_data_file(db, user_id, data_file_id, load_schema=False)
    data_file.deleted_at = datetime.now(timezone.utc)
    await db.execute(
        sa.delete(DataFileSchema).where(DataFileSchema.data_file_id == data_file_id)
    )
    await db.commit()


async def list_data_file_names(db: AsyncSession, user_id: UUID) -> list[str]:
    """Return filenames of all ready data files — lightweight query for routing decisions."""
    result = await db.execute(
        sa.select(DataFile.filename).where(
            DataFile.user_id == user_id,
            DataFile.deleted_at.is_(None),
            DataFile.status == "ready",
        )
    )
    return [row[0] for row in result.all()]


async def get_file_schemas_for_routing(
    db: AsyncSession, user_id: UUID
) -> list[dict]:
    """
    Compact schema info for all ready files — used to build LLM context.

    Returns [{file_id, filename, columns: [{name, type}]}].
    No sample_values — keeps the payload small enough to include in a prompt.
    """
    files = await list_data_files(db, user_id)
    return [
        {
            "file_id": str(f.id),
            "filename": f.filename,
            "columns": [
                {"name": c.column_name, "type": c.column_type}
                for c in (f.schema_columns or [])
            ],
        }
        for f in files
        if f.status == "ready"
    ]


# ── Response helpers ───────────────────────────────────────────────────────────


def to_file_response_dict(data_file: DataFile) -> dict:
    """
    Build a response dict from a DataFile ORM object.

    data_file.schema_columns must already be loaded (use selectinload).
    """
    cols = data_file.schema_columns
    return {
        "id": data_file.id,
        "filename": data_file.filename,
        "file_size": data_file.file_size,
        "content_type": data_file.content_type,
        "status": data_file.status,
        "processing_error": data_file.processing_error,
        "row_count": data_file.row_count,
        "column_count": len(cols) if cols is not None else 0,
        "uploaded_at": data_file.uploaded_at,
    }
