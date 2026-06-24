"""Pydantic schemas for data_files endpoints (v2 data analysis)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DataFileSchemaColumn(BaseModel):
    """One column in a data file's inferred schema."""

    column_name: str
    column_type: str
    sample_values: list[Any] | None = None
    null_count: int | None = None
    unique_count: int | None = None

    model_config = {"from_attributes": True}


class DataFileResponse(BaseModel):
    """List / upload response — never includes raw file bytes."""

    id: UUID
    filename: str
    file_size: int
    content_type: str
    status: str
    processing_error: str | None
    row_count: int | None
    # Populated by the service layer (len of associated schema rows)
    column_count: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DataFileWithSchema(DataFileResponse):
    """Extends DataFileResponse with per-column schema details."""

    columns: list[DataFileSchemaColumn] = []


class DataFileStatusResponse(BaseModel):
    """Lightweight polling response for upload status checks."""

    id: UUID
    status: str
    processing_error: str | None
    row_count: int | None
    column_count: int

    model_config = {"from_attributes": True}
