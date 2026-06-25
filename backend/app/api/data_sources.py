"""Data source endpoints — CRUD and connection testing.

Routes:
  GET    /api/data-sources                   — list all data sources (no credentials)
  POST   /api/data-sources                   — create a new data source
  GET    /api/data-sources/{source_id}       — get one source with schema_cache
  PATCH  /api/data-sources/{source_id}       — update name and/or connection config
  DELETE /api/data-sources/{source_id}       — hard delete
  POST   /api/data-sources/{source_id}/test  — test connectivity (rate-limited)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.data_source import (
    CONFIG_MODEL_MAP,
    DataSourceCreate,
    DataSourceResponse,
    DataSourceUpdate,
    DataSourceWithSchema,
    TestConnectionResponse,
    _SENSITIVE_FIELDS,
)
from app.services import data_source_service

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])
logger = logging.getLogger(__name__)


def _assert_no_credentials(response_dict: dict) -> None:
    """Raise AssertionError if any sensitive credential key leaks into a response dict."""
    leaked = _SENSITIVE_FIELDS.intersection(response_dict.keys())
    assert not leaked, f"Credential key(s) leaked into API response: {leaked}"


@router.get(
    "",
    response_model=list[DataSourceResponse],
    summary="List data sources",
)
async def list_data_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DataSourceResponse]:
    """Return all data sources for the authenticated user, newest first. Credentials are never included."""
    sources = await data_source_service.list_data_sources(db, current_user.id)
    responses = [DataSourceResponse.model_validate(ds) for ds in sources]
    for r in responses:
        _assert_no_credentials(r.model_dump())
    return responses


@router.post(
    "",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a data source",
)
async def create_data_source(
    body: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataSourceResponse:
    """
    Register a new external data source. connection_config is validated against the
    declared source_type, then encrypted at rest. Credentials are never returned.
    """
    config_model = CONFIG_MODEL_MAP[body.source_type]
    try:
        config_model.model_validate(body.connection_config)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        )

    ds = await data_source_service.create_data_source(
        db,
        user_id=current_user.id,
        name=body.name,
        source_type=body.source_type,
        connection_config=body.connection_config,
    )
    return DataSourceResponse.model_validate(ds)


@router.get(
    "/{source_id}",
    response_model=DataSourceWithSchema,
    summary="Get a data source with schema",
)
async def get_data_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataSourceWithSchema:
    """Return one data source including its last-introspected schema. Credentials are never included."""
    ds = await data_source_service.get_data_source(db, current_user.id, source_id)
    response = DataSourceWithSchema.model_validate(ds)
    _assert_no_credentials(response.model_dump())
    return response


@router.patch(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Update a data source",
)
async def update_data_source(
    source_id: UUID,
    body: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DataSourceResponse:
    """Update the name and/or connection config of a data source."""
    if body.connection_config is not None:
        # Need source_type from DB to validate the new config structure.
        existing = await data_source_service.get_data_source(db, current_user.id, source_id)
        config_model = CONFIG_MODEL_MAP[existing.source_type]
        try:
            config_model.model_validate(body.connection_config)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )

    ds = await data_source_service.update_data_source(
        db,
        user_id=current_user.id,
        source_id=source_id,
        name=body.name,
        connection_config=body.connection_config,
    )
    return DataSourceResponse.model_validate(ds)


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a data source",
)
async def delete_data_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Hard-delete a data source and all associated state."""
    await data_source_service.delete_data_source(db, current_user.id, source_id)


@router.post(
    "/{source_id}/test",
    response_model=TestConnectionResponse,
    summary="Test a data source connection",
)
@limiter.limit("10/minute")
async def test_connection(
    source_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestConnectionResponse:
    """
    Attempt to connect to the external data source and return the result.

    Updates last_tested_at, last_test_status, and schema_cache on success.
    Rate-limited to 10 requests per minute to prevent credential-stuffing against
    external systems.
    """
    result = await data_source_service.test_connection(db, current_user.id, source_id)
    return TestConnectionResponse(**result)
