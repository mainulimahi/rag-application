"""Data source service — CRUD and connection testing for external data sources.

All operations are scoped to user_id (multi-tenancy security boundary).
Credentials in connection_config are Fernet-encrypted before storage and
decrypted only inside get_decrypted_config() — the sole decryption callsite.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt, encrypt
from app.models.data_source import DataSource

logger = logging.getLogger(__name__)

_VALID_SOURCE_TYPES = frozenset(
    {"s3", "gcs", "azure_blob", "postgresql", "mysql", "sqlite", "api"}
)


# ── CRUD ───────────────────────────────────────────────────────────────────────


async def create_data_source(
    db: AsyncSession,
    user_id: UUID,
    name: str,
    source_type: str,
    connection_config: dict,
) -> DataSource:
    """Create and persist a data source. connection_config is encrypted before storage."""
    if source_type not in _VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported source_type '{source_type}'",
        )
    ds = DataSource(
        user_id=user_id,
        name=name,
        source_type=source_type,
        connection_config=encrypt(json.dumps(connection_config)),
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds


async def list_data_sources(db: AsyncSession, user_id: UUID) -> list[DataSource]:
    """Return all data sources for user_id, newest first."""
    result = await db.execute(
        sa.select(DataSource)
        .where(DataSource.user_id == user_id)
        .order_by(DataSource.created_at.desc())
    )
    return list(result.scalars().all())


async def get_data_source(
    db: AsyncSession, user_id: UUID, source_id: UUID
) -> DataSource:
    """Return a data source only if it belongs to user_id; raise 404 otherwise."""
    result = await db.execute(
        sa.select(DataSource).where(
            DataSource.id == source_id,
            DataSource.user_id == user_id,
        )
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
    return ds


def get_decrypted_config(data_source: DataSource) -> dict:
    """Decrypt and parse connection_config — the only place decryption happens."""
    return json.loads(decrypt(data_source.connection_config))


async def update_data_source(
    db: AsyncSession,
    user_id: UUID,
    source_id: UUID,
    name: str | None,
    connection_config: dict | None,
) -> DataSource:
    """Update name and/or connection_config after verifying ownership."""
    ds = await get_data_source(db, user_id, source_id)
    if name is not None:
        ds.name = name
    if connection_config is not None:
        ds.connection_config = encrypt(json.dumps(connection_config))
    ds.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ds)
    return ds


async def delete_data_source(
    db: AsyncSession, user_id: UUID, source_id: UUID
) -> None:
    """Hard-delete a data source after verifying ownership."""
    ds = await get_data_source(db, user_id, source_id)
    await db.delete(ds)
    await db.commit()


# ── Connection testing ─────────────────────────────────────────────────────────


async def test_connection(
    db: AsyncSession, user_id: UUID, source_id: UUID
) -> dict:
    """
    Test connectivity to the external data source and persist the result.

    Updates last_tested_at, last_test_status, last_test_error, and schema_cache.
    Credentials are never included in the return value.
    """
    ds = await get_data_source(db, user_id, source_id)
    config = get_decrypted_config(ds)
    result: dict

    try:
        result = _run_connection_test(ds.source_type, config)
        ds.last_test_status = "ok"
        ds.last_test_error = None
        schema_cache = result.pop("schema_cache", None)
        if schema_cache is not None:
            ds.schema_cache = json.dumps(schema_cache)
    except Exception as exc:
        error_msg = str(exc)[:500]
        result = {"status": "error", "message": str(exc)[:200]}
        ds.last_test_status = "error"
        ds.last_test_error = error_msg
        logger.warning("Connection test failed for source %s: %s", source_id, error_msg)

    ds.last_tested_at = datetime.now(timezone.utc)
    await db.commit()
    return result


def _run_connection_test(source_type: str, config: dict) -> dict:
    """
    Dispatch synchronous connection test by source_type.

    Runs on the event loop — acceptable for admin-tier, user-triggered, low-frequency calls.
    Each connector has a hard timeout (connect_timeout / httpx timeout).
    Cloud storage connectors (s3, gcs, azure_blob) require their respective SDKs:
    boto3, google-cloud-storage, azure-storage-blob. If not installed the test returns
    an error message describing the missing package.
    """
    handlers = {
        "postgresql": _test_postgresql,
        "mysql": _test_mysql,
        "sqlite": _test_sqlite,
        "s3": _test_s3,
        "gcs": _test_gcs,
        "azure_blob": _test_azure_blob,
        "api": _test_api,
    }
    return handlers[source_type](config)


def _test_postgresql(config: dict) -> dict:
    import psycopg2  # already in requirements (psycopg2-binary)

    conn = psycopg2.connect(
        host=config["host"],
        port=config.get("port", 5432),
        dbname=config["database"],
        user=config["username"],
        password=config["password"],
        sslmode="require" if config.get("ssl") else "disable",
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = 'public'"
            )
            tables = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    schema_cache = {"tables": tables, "table_count": len(tables)}
    return {
        "status": "ok",
        "message": f"Connected — found {len(tables)} tables",
        "tables_found": len(tables),
        "schema_cache": schema_cache,
    }


def _test_mysql(config: dict) -> dict:
    import pymysql  # requires pymysql in requirements.txt

    conn = pymysql.connect(
        host=config["host"],
        port=config.get("port", 3306),
        db=config["database"],
        user=config["username"],
        password=config["password"],
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    schema_cache = {"tables": tables, "table_count": len(tables)}
    return {
        "status": "ok",
        "message": f"Connected — found {len(tables)} tables",
        "tables_found": len(tables),
        "schema_cache": schema_cache,
    }


def _test_sqlite(config: dict) -> dict:
    import duckdb  # requires duckdb in requirements.txt

    conn = duckdb.connect(config["file_path"])
    try:
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        tables = [row[0] for row in result]
    finally:
        conn.close()

    schema_cache = {"tables": tables, "table_count": len(tables)}
    return {
        "status": "ok",
        "message": f"Connected — found {len(tables)} tables",
        "tables_found": len(tables),
        "schema_cache": schema_cache,
    }


def _test_s3(config: dict) -> dict:
    import boto3  # optional: pip install boto3

    client = boto3.client(
        "s3",
        region_name=config["region"],
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
    )
    response = client.list_objects_v2(
        Bucket=config["bucket"],
        Prefix=config.get("prefix", ""),
        MaxKeys=20,
    )
    files = [obj["Key"] for obj in response.get("Contents", [])]
    schema_cache = {
        "sample_files": files[:5],
        "file_count": response.get("KeyCount", 0),
    }
    return {
        "status": "ok",
        "message": f"Connected — found {len(files)} objects",
        "schema_cache": schema_cache,
    }


def _test_gcs(config: dict) -> dict:
    import json as _json

    from google.cloud import storage  # optional: pip install google-cloud-storage

    client = storage.Client.from_service_account_info(
        _json.loads(config["service_account_json"])
    )
    blobs = list(
        client.list_blobs(
            config["bucket"],
            prefix=config.get("prefix") or None,
            max_results=20,
        )
    )
    files = [b.name for b in blobs]
    schema_cache = {"sample_files": files[:5], "file_count": len(files)}
    return {
        "status": "ok",
        "message": f"Connected — found {len(files)} objects",
        "schema_cache": schema_cache,
    }


def _test_azure_blob(config: dict) -> dict:
    from itertools import islice

    from azure.storage.blob import BlobServiceClient  # optional: pip install azure-storage-blob

    client = BlobServiceClient(
        account_url=f"https://{config['account_name']}.blob.core.windows.net",
        credential=config["account_key"],
    )
    container_client = client.get_container_client(config["container"])
    blobs = list(
        islice(
            container_client.list_blobs(name_starts_with=config.get("prefix") or None),
            20,
        )
    )
    files = [b.name for b in blobs]
    schema_cache = {"sample_files": files[:5], "file_count": len(files)}
    return {
        "status": "ok",
        "message": f"Connected — found {len(files)} objects",
        "schema_cache": schema_cache,
    }


def _test_api(config: dict) -> dict:
    import httpx  # requires httpx in requirements.txt

    headers = dict(config.get("headers") or {})
    auth_type = config.get("auth_type", "none")
    auth_value = config.get("auth_value")
    if auth_type == "bearer" and auth_value:
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "api_key" and auth_value:
        headers["X-API-Key"] = auth_value

    response = httpx.get(config["base_url"], headers=headers, timeout=10)
    response.raise_for_status()
    return {
        "status": "ok",
        "message": f"Connected — HTTP {response.status_code}",
    }
