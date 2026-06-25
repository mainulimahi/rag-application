"""Pydantic schemas for data_sources endpoints (v2 data analysis)."""

import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# ── Per-source-type connection config models ──────────────────────────────────
# These document expected fields; the service layer validates the incoming dict
# against the appropriate model before encrypting and storing it.

_SENSITIVE_FIELDS = frozenset(
    {"password", "secret_access_key", "account_key", "service_account_json", "auth_value"}
)

SOURCE_TYPE = Literal["s3", "gcs", "azure_blob", "postgresql", "mysql", "sqlite", "api"]


class PostgreSQLConfig(BaseModel):
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    ssl: bool = False


class MySQLConfig(BaseModel):
    host: str
    port: int = 3306
    database: str
    username: str
    password: str


class SQLiteConfig(BaseModel):
    file_path: str

    @field_validator("file_path")
    @classmethod
    def _validate_file_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("file_path must not contain '..'")
        if not v.startswith("/"):
            raise ValueError("file_path must be an absolute path starting with '/'")
        return v


class S3Config(BaseModel):
    bucket: str
    prefix: str = ""
    region: str
    access_key_id: str
    secret_access_key: str


class GCSConfig(BaseModel):
    bucket: str
    prefix: str = ""
    service_account_json: str


class AzureBlobConfig(BaseModel):
    account_name: str
    account_key: str
    container: str
    prefix: str = ""


class APIConfig(BaseModel):
    base_url: str
    auth_type: Literal["none", "bearer", "api_key"] = "none"
    auth_value: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


# Map used by the service layer to validate connection_config per source_type
CONFIG_MODEL_MAP: dict[str, type[BaseModel]] = {
    "postgresql": PostgreSQLConfig,
    "mysql": MySQLConfig,
    "sqlite": SQLiteConfig,
    "s3": S3Config,
    "gcs": GCSConfig,
    "azure_blob": AzureBlobConfig,
    "api": APIConfig,
}


# ── Request / Response models ─────────────────────────────────────────────────

class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: SOURCE_TYPE
    connection_config: dict[str, Any]


class DataSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    connection_config: dict[str, Any] | None = None


class DataSourceResponse(BaseModel):
    """Safe response — never exposes connection credentials."""

    id: UUID
    name: str
    source_type: str
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceWithSchema(DataSourceResponse):
    """Extends DataSourceResponse with the last-introspected schema (if available)."""

    schema_cache: dict[str, Any] | None = None

    @field_validator("schema_cache", mode="before")
    @classmethod
    def _parse_schema_cache(cls, v: Any) -> dict | None:
        """Auto-parse JSON strings stored in the TEXT column back to dict."""
        if isinstance(v, str):
            return json.loads(v) if v else None
        return v


class TestConnectionResponse(BaseModel):
    status: Literal["ok", "error"]
    message: str
    tables_found: int | None = None
    schema_summary: dict[str, Any] | None = None


class MaskedConfig:
    """Utility — returns a copy of a config dict with sensitive fields replaced by '***'."""

    @staticmethod
    def mask(config: dict[str, Any]) -> dict[str, Any]:
        return {
            k: "***" if k in _SENSITIVE_FIELDS else v
            for k, v in config.items()
        }
