"""Pydantic schemas for the document upload and management endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Returned immediately after a file is accepted for background processing."""

    id: UUID
    filename: str
    content_type: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """One row in the GET /api/documents list — never includes raw file bytes."""

    id: UUID
    filename: str
    content_type: str
    status: str
    processing_error: str | None
    chunk_count: int
    uploaded_at: datetime


class DocumentStatusResponse(BaseModel):
    """Returned by GET /api/documents/{id}/status for polling."""

    id: UUID
    status: str
    processing_error: str | None
    chunk_count: int
