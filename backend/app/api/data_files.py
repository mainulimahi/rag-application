"""Data file endpoints — upload, schema, status, and delete.

Routes:
  POST   /api/data-files/upload        — multipart upload; background schema extraction
  GET    /api/data-files               — list files with full schema
  GET    /api/data-files/{id}/schema   — detailed schema with sample values
  GET    /api/data-files/{id}/status   — lightweight processing status poll
  DELETE /api/data-files/{id}          — soft delete + hard-delete schema rows
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.data_file import (
    DataFileResponse,
    DataFileSchemaColumn,
    DataFileStatusResponse,
    DataFileWithSchema,
)
from app.services import data_file_service

router = APIRouter(prefix="/api/data-files", tags=["data-files"])
logger = logging.getLogger(__name__)


def _build_with_schema(data_file) -> DataFileWithSchema:
    """Build DataFileWithSchema from a DataFile ORM object with schema_columns loaded."""
    return DataFileWithSchema(
        **data_file_service.to_file_response_dict(data_file),
        columns=[
            DataFileSchemaColumn.model_validate(c)
            for c in (data_file.schema_columns or [])
        ],
    )


@router.post(
    "/upload",
    response_model=DataFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a data file for analysis",
)
@limiter.limit("20/minute")
async def upload_data_file(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataFileResponse:
    """
    Accept a file (CSV, TSV, Parquet, Excel, JSON; max 20 MB) and schedule background
    schema extraction. Returns 201 immediately with status='processing'.

    Poll GET /api/data-files/{id}/status until status is 'ready' or 'failed'.
    """
    file_bytes = await file.read()
    data_file = await data_file_service.upload_data_file(
        db,
        user_id=current_user.id,
        filename=file.filename or "upload",
        file_bytes=file_bytes,
        content_type=file.content_type or "application/octet-stream",
        background_tasks=background_tasks,
    )
    # schema_columns not yet loaded (background task hasn't run); column_count is 0
    return DataFileResponse(
        id=data_file.id,
        filename=data_file.filename,
        file_size=data_file.file_size,
        content_type=data_file.content_type,
        status=data_file.status,
        processing_error=data_file.processing_error,
        row_count=data_file.row_count,
        column_count=0,
        uploaded_at=data_file.uploaded_at,
    )


@router.get(
    "",
    response_model=list[DataFileWithSchema],
    summary="List data files with schemas",
)
async def list_data_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DataFileWithSchema]:
    """Return all data files for the authenticated user, newest first, with full schema."""
    files = await data_file_service.list_data_files(db, current_user.id)
    return [_build_with_schema(f) for f in files]


@router.get(
    "/{file_id}/schema",
    response_model=DataFileWithSchema,
    summary="Get data file schema with sample values",
)
async def get_data_file_schema(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataFileWithSchema:
    """Return the full schema for one data file, including per-column sample values."""
    data_file = await data_file_service.get_data_file(
        db, current_user.id, file_id, load_schema=True
    )
    return _build_with_schema(data_file)


@router.get(
    "/{file_id}/status",
    response_model=DataFileStatusResponse,
    summary="Poll data file processing status",
)
async def get_data_file_status(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataFileStatusResponse:
    """
    Lightweight status check — poll after upload until status is 'ready' or 'failed'.
    """
    status_dict = await data_file_service.get_data_file_status(
        db, current_user.id, file_id
    )
    return DataFileStatusResponse(**status_dict)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a data file",
)
async def delete_data_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete a data file and immediately hard-delete all its schema rows."""
    await data_file_service.delete_data_file(db, current_user.id, file_id)
