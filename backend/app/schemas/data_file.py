"""Pydantic schemas for data_files endpoints (v2 data analysis)."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


class DataFileSchemaColumn(BaseModel):
    """One column in a data file's inferred schema."""

    column_name: str
    column_type: str
    sample_values: list[Any] | None = None
    null_count: int | None = None
    unique_count: int | None = None

    model_config = {"from_attributes": True}

    @field_validator("sample_values", mode="before")
    @classmethod
    def _parse_sample_values(cls, v: Any) -> list | None:
        """Auto-parse JSON strings stored in the TEXT column back to list."""
        if isinstance(v, str):
            return json.loads(v) if v else None
        return v


class DataFileResponse(BaseModel):
    """List / upload response — never includes raw file bytes."""

    id: UUID
    filename: str
    file_size: int
    content_type: str
    status: str
    processing_error: str | None
    row_count: int | None
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
