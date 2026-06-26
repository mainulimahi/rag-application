"""DuckDB service — schema introspection and query execution for data files and external sources.

All file I/O goes through /tmp/duckdb_work/ with UUID-prefixed temp files that are
always cleaned up in finally blocks. Callers should not catch exceptions from
extract_schema/query_file — they raise ValueError on bad input and TimeoutError
on query timeout; the service layer converts these to HTTPExceptions.
"""

from __future__ import annotations

import decimal
import io
import json
import logging
import math
import re
import threading
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".parquet", ".xlsx", ".xls", ".json"}
MAX_RESULT_ROWS = 500
QUERY_TIMEOUT_SECONDS = 30
TEMP_DIR = Path("/tmp/duckdb_work")


# ── Temp file management ───────────────────────────────────────────────────────


def _ensure_temp_dir() -> None:
    TEMP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def _write_temp_file(file_bytes: bytes, filename: str) -> Path:
    """Write bytes to a UUID-prefixed temp file; return its Path."""
    _ensure_temp_dir()
    safe_name = re.sub(r"[^\w.\-]", "_", Path(filename).name) or "upload"
    if ".." in safe_name:
        raise ValueError("Invalid filename")
    temp_path = TEMP_DIR / f"{uuid4().hex}_{safe_name}"
    if not str(temp_path).startswith(str(TEMP_DIR)):
        raise ValueError("Invalid file path")
    temp_path.write_bytes(file_bytes)
    temp_path.chmod(0o600)
    return temp_path


def _cleanup_temp_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("Failed to delete temp file %s: %s", path, exc)


def cleanup_orphaned_temp_files() -> None:
    """Delete temp files older than 1 hour. Called on app startup."""
    try:
        _ensure_temp_dir()
    except Exception as exc:
        logger.warning("Could not ensure temp dir on startup: %s", exc)
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    for f in TEMP_DIR.iterdir():
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                logger.info("Cleaned up orphaned temp file: %s", f.name)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning("Could not clean up temp file %s: %s", f.name, exc)


# ── Query timeout ──────────────────────────────────────────────────────────────


def _execute_with_timeout(
    conn: duckdb.DuckDBPyConnection, sql: str, timeout: float
) -> pd.DataFrame:
    """Execute SQL; raise TimeoutError if it exceeds `timeout` seconds."""
    result_box: list[pd.DataFrame] = []
    error_box: list[BaseException] = []
    done = threading.Event()

    def _run() -> None:
        try:
            result_box.append(conn.execute(sql).df())
        except Exception as exc:
            error_box.append(exc)
        finally:
            done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    if not done.wait(timeout=timeout):
        try:
            conn.interrupt()
        except Exception:
            pass
        raise TimeoutError(f"Query timed out after {timeout} seconds")
    if error_box:
        raise error_box[0]
    return result_box[0]


# ── Format detection ───────────────────────────────────────────────────────────


def _build_query_expr(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    ext: str,
    file_bytes: bytes,
) -> str:
    """
    Return a DuckDB query expression for the given file extension.

    For xlsx/xls, tries the DuckDB excel extension first; falls back to
    openpyxl → registered DataFrame view if that fails.
    """
    safe = str(path).replace("'", "''")

    if ext in (".csv", ".tsv"):
        return f"read_csv('{safe}', auto_detect=True)"
    if ext == ".parquet":
        return f"read_parquet('{safe}')"
    if ext == ".json":
        return f"read_json('{safe}')"
    if ext in (".xlsx", ".xls"):
        try:
            conn.execute("INSTALL excel; LOAD excel;")
            return f"read_xlsx('{safe}')"
        except Exception:
            if ext == ".xls":
                raise ValueError(
                    "Legacy .xls format is not supported. Convert to .xlsx and try again."
                )
            # Multi-sheet selection: find the sheet with the most rows.
            xl = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
            sheet_names = xl.sheet_names

            best_sheet = sheet_names[0]
            best_rows = 0
            for sheet in sheet_names:
                try:
                    xl.parse(sheet, nrows=5)  # verify sheet is readable before full load
                    full_df = xl.parse(sheet)
                    if len(full_df) > best_rows:
                        best_rows = len(full_df)
                        best_sheet = sheet
                except Exception:
                    continue

            logger.info(
                "Excel: selected sheet '%s' (%d rows) from %d sheets",
                best_sheet, best_rows, len(sheet_names),
            )
            df_excel = xl.parse(best_sheet)
            conn.register("_excel_view", df_excel)
            return "_excel_view"

    raise ValueError(f"Unsupported extension: {ext}")


# ── Schema extraction ──────────────────────────────────────────────────────────


def extract_schema(file_bytes: bytes, filename: str) -> dict:
    """
    Extract column schema and per-column statistics from a data file.

    Returns:
        {
            "columns": [{"name", "type", "sample_values", "null_count", "unique_count"}],
            "row_count": int,
        }
    Raises ValueError on unsupported format or read failure.
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file format '{ext}'")

    path = _write_temp_file(file_bytes, filename)
    try:
        conn = duckdb.connect()
        try:
            qexpr = _build_query_expr(conn, path, ext, file_bytes)

            try:
                row_count: int = conn.execute(f"SELECT COUNT(*) FROM {qexpr}").fetchone()[0]
                describe_rows = conn.execute(f"DESCRIBE SELECT * FROM {qexpr}").fetchall()
            except duckdb.Error as exc:
                raise ValueError(f"Could not read {filename}: {exc}") from exc

            raw_cols = [(r[0], r[1]) for r in describe_rows[:50]]
            columns = []
            for col_name, col_type in raw_cols:
                safe_col = col_name.replace('"', '""')
                cq = f'"{safe_col}"'

                try:
                    sample_rows = conn.execute(
                        f"SELECT {cq} FROM {qexpr} WHERE {cq} IS NOT NULL LIMIT 5"
                    ).fetchall()
                    sample_values = [_serialize_value(r[0]) for r in sample_rows]
                except Exception:
                    sample_values = []

                try:
                    null_count: int | None = conn.execute(
                        f"SELECT COUNT(*) FROM {qexpr} WHERE {cq} IS NULL"
                    ).fetchone()[0]
                except Exception:
                    null_count = None

                try:
                    unique_count: int | None = conn.execute(
                        f"SELECT COUNT(DISTINCT {cq}) FROM {qexpr}"
                    ).fetchone()[0]
                except Exception:
                    unique_count = None

                columns.append(
                    {
                        "name": col_name,
                        "type": col_type,
                        "sample_values": sample_values,
                        "null_count": null_count,
                        "unique_count": unique_count,
                    }
                )
        finally:
            conn.close()
    finally:
        _cleanup_temp_file(path)

    return {"columns": columns, "row_count": row_count}


# ── File query ─────────────────────────────────────────────────────────────────


def query_file(file_bytes: bytes, filename: str, sql: str, user_id: object = None) -> dict:
    """
    Execute user SQL against an uploaded file.

    References to the original filename in the SQL are replaced with the actual
    temp file path before execution.

    Returns:
        {columns, rows, row_count, total_row_count, truncated, summary_stats}
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file format '{ext}'")

    path = _write_temp_file(file_bytes, filename)
    try:
        conn = duckdb.connect()
        try:
            _build_query_expr(conn, path, ext, file_bytes)  # registers excel view if needed
            safe_path = str(path)

            # Replace all quoted filename references (handles single and double quotes,
            # case-insensitive, covers read_csv/read_excel/read_auto/etc.)
            escaped_filename = re.escape(filename)
            sql_with_path = re.sub(
                rf"(['\"]){escaped_filename}(['\"])",
                f"'{safe_path}'",
                sql,
                flags=re.IGNORECASE,
            )
            # Catch any remaining bare occurrences the regex missed
            if filename in sql_with_path:
                sql_with_path = sql_with_path.replace(f"'{filename}'", f"'{safe_path}'")
                sql_with_path = sql_with_path.replace(f'"{filename}"', f"'{safe_path}'")

            logger.debug("Executing SQL: %s", sql_with_path[:200])
            try:
                df = _execute_with_timeout(conn, sql_with_path, QUERY_TIMEOUT_SECONDS)
            except TimeoutError:
                raise
            except duckdb.Error as exc:
                raise ValueError(f"Query failed: {exc}") from exc
        finally:
            conn.close()
    finally:
        _cleanup_temp_file(path)

    result = _wrap_dataframe(df)
    logger.info(
        "DuckDB query executed — user_id=%s, source='%s', rows=%d, truncated=%s, sql_preview='%s...'",
        user_id,
        filename,
        result["row_count"],
        result["truncated"],
        sql[:80],
    )
    return result


# ── Data source query ──────────────────────────────────────────────────────────


def query_data_source(
    config: dict, source_type: str, sql: str, source_name: str = "", user_id: object = None
) -> dict:
    """
    Execute user SQL against an external data source.

    Same return shape as query_file: {columns, rows, row_count, total_row_count,
    truncated, summary_stats}.
    """
    dispatch = {
        "postgresql": _query_postgresql,
        "mysql": _query_mysql,
        "sqlite": _query_sqlite,
        "s3": _query_s3,
        "api": _query_api,
    }
    if source_type not in dispatch:
        raise ValueError(f"query_data_source does not support source_type '{source_type}'")
    df = dispatch[source_type](config, sql)
    result = _wrap_dataframe(df)
    logger.info(
        "DuckDB query executed — user_id=%s, source='%s' (%s), rows=%d, truncated=%s, sql_preview='%s...'",
        user_id,
        source_name,
        source_type,
        result["row_count"],
        result["truncated"],
        sql[:80],
    )
    return result


def _query_postgresql(config: dict, sql: str) -> pd.DataFrame:
    from urllib.parse import quote_plus

    user = quote_plus(config["username"])
    pw = quote_plus(config["password"])
    conn_str = (
        f"postgresql://{user}:{pw}"
        f"@{config['host']}:{config.get('port', 5432)}/{config['database']}"
    )
    conn = duckdb.connect()
    try:
        conn.execute("INSTALL postgres; LOAD postgres;")
        conn.execute(f"ATTACH '{conn_str}' AS ext_db (TYPE POSTGRES, READ_ONLY)")
        return _execute_with_timeout(conn, sql, QUERY_TIMEOUT_SECONDS)
    finally:
        conn.close()


def _query_mysql(config: dict, sql: str) -> pd.DataFrame:
    import pymysql

    cx = pymysql.connect(
        host=config["host"],
        port=config.get("port", 3306),
        db=config["database"],
        user=config["username"],
        password=config["password"],
        connect_timeout=10,
    )
    try:
        with cx.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in (cur.description or [])]
            rows = cur.fetchmany(MAX_RESULT_ROWS + 1)
        return pd.DataFrame(rows, columns=cols)
    finally:
        cx.close()


def _query_sqlite(config: dict, sql: str) -> pd.DataFrame:
    conn = duckdb.connect()
    try:
        conn.execute(
            f"ATTACH '{config['file_path']}' AS ext_db (TYPE SQLITE, READ_ONLY)"
        )
        return _execute_with_timeout(conn, sql, QUERY_TIMEOUT_SECONDS)
    finally:
        conn.close()


def _query_s3(config: dict, sql: str) -> pd.DataFrame:
    conn = duckdb.connect()
    try:
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        conn.execute(f"SET s3_region='{config['region']}'")
        conn.execute(f"SET s3_access_key_id='{config['access_key_id']}'")
        conn.execute(f"SET s3_secret_access_key='{config['secret_access_key']}'")
        return _execute_with_timeout(conn, sql, QUERY_TIMEOUT_SECONDS)
    finally:
        conn.close()


def _query_api(config: dict, sql: str) -> pd.DataFrame:
    import httpx

    headers = dict(config.get("headers") or {})
    auth_type = config.get("auth_type", "none")
    auth_value = config.get("auth_value")
    if auth_type == "bearer" and auth_value:
        headers["Authorization"] = f"Bearer {auth_value}"
    elif auth_type == "api_key" and auth_value:
        headers["X-API-Key"] = auth_value

    response = httpx.get(config["base_url"], headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list) and data:
        df_api = pd.DataFrame(data)
    elif isinstance(data, dict):
        df_api = pd.DataFrame([data])
    else:
        raise ValueError("API response is not tabular — cannot query it with SQL")

    csv_bytes = df_api.to_csv(index=False).encode("utf-8")
    csv_path = _write_temp_file(csv_bytes, "api_response.csv")
    try:
        conn = duckdb.connect()
        safe = str(csv_path).replace("'", "''")
        sql_patched = sql.replace(config["base_url"], safe)
        try:
            return _execute_with_timeout(conn, sql_patched, QUERY_TIMEOUT_SECONDS)
        finally:
            conn.close()
    finally:
        _cleanup_temp_file(csv_path)


# ── Result helpers ─────────────────────────────────────────────────────────────


def _wrap_dataframe(df: pd.DataFrame) -> dict:
    """Apply MAX_RESULT_ROWS truncation, compute stats, serialize to JSON-safe dict."""
    total_row_count = len(df)
    truncated = total_row_count > MAX_RESULT_ROWS
    summary_stats = generate_summary_stats(df)  # stats on full result

    if truncated:
        df = df.head(MAX_RESULT_ROWS)

    rows = [[_serialize_value(cell) for cell in row] for row in df.values.tolist()]

    return {
        "columns": list(df.columns),
        "rows": rows,
        "row_count": len(df),
        "total_row_count": total_row_count,
        "truncated": truncated,
        "summary_stats": summary_stats,
    }


def generate_summary_stats(df: pd.DataFrame) -> dict:
    """Per-column summary stats. NaN/inf replaced with None for JSON safety."""
    stats: dict = {}
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        if pd.api.types.is_numeric_dtype(series):
            stats[col] = {
                "min": _serialize_value(non_null.min() if len(non_null) else None),
                "max": _serialize_value(non_null.max() if len(non_null) else None),
                "mean": _serialize_value(non_null.mean() if len(non_null) else None),
                "median": _serialize_value(non_null.median() if len(non_null) else None),
                "std": _serialize_value(non_null.std() if len(non_null) else None),
                "non_null_count": int(len(non_null)),
            }
        else:
            vc = non_null.astype(str).value_counts().head(5)
            stats[col] = {
                "unique_count": int(non_null.nunique()),
                "top_5": [{"value": _serialize_value(v), "count": int(c)} for v, c in vc.items()],
            }
    return stats


def _serialize_value(val: object) -> object:
    """Convert a single cell value to a JSON-safe Python primitive."""
    if val is None:
        return None
    if isinstance(val, (datetime, date, time)):
        return val.isoformat()
    if isinstance(val, decimal.Decimal):
        return float(val)
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        v = float(val)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def _safe_scalar(v: object) -> object:
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    try:
        if math.isnan(float(v)) or math.isinf(float(v)):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    return v


def _safe_value(v: object) -> object:
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v
