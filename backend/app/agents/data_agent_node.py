"""Data analysis agent node — routes data queries through DuckDB.

Selects relevant data sources via LLM, generates validated DuckDB SQL, executes
queries against uploaded files and connected sources, and returns structured
results for the synthesis node to narrate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from uuid import UUID

import sqlalchemy as sa
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LLMProviderError, RateLimitError
from app.models.data_file import DataFile
from app.services import data_file_service, data_source_service, duckdb_service
from app.services.llm_factory import get_llm, get_sql_llm

logger = logging.getLogger(__name__)

_FORBIDDEN_KEYWORDS = [
    "drop", "delete", "update", "insert", "create", "alter",
    "truncate", "exec", "execute", "copy", "union",
    "xp_", "sp_", "pg_", "information_schema", "pg_catalog",
    "--", "/*",
]

# These keywords are matched using word boundaries to avoid false positives.
_WORD_BOUNDARY_KEYWORDS = frozenset(
    {"drop", "delete", "update", "insert", "create", "alter",
     "truncate", "exec", "execute", "copy", "union"}
)


async def select_relevant_sources(
    user_query: str,
    data_files: list[dict],
    data_connections: list[dict],
) -> dict:
    """Ask Gemini which data sources are relevant to answer the user query.

    Returns {"file_ids": [...], "source_ids": [...], "reason": str}.
    Falls back to empty lists on parse errors.
    """
    if not data_files and not data_connections:
        return {"file_ids": [], "source_ids": [], "reason": "no_sources"}

    files_context = "\n".join(
        "File '{}': columns [{}]".format(
            f["filename"],
            ", ".join(f"{c['name']}({c['type']})" for c in f["columns"]),
        )
        for f in data_files
    ) or "(none)"

    connections_context = "\n".join(
        "Connection '{}' ({}): {}".format(
            c["name"],
            c["source_type"],
            c.get("schema_summary") or "schema not yet introspected",
        )
        for c in data_connections
    ) or "(none)"

    prompt = (
        "You are a data routing assistant. Given a user query and available data sources, "
        "decide which sources (if any) are relevant to answer the query.\n\n"
        f"User query: {user_query}\n\n"
        f"Available data files:\n{files_context}\n\n"
        f"Available connections:\n{connections_context}\n\n"
        'Return ONLY valid JSON in this exact format:\n'
        '{"file_ids": ["id1", "id2"], "source_ids": ["id1"], "reason": "brief explanation"}\n\n'
        "Return empty lists if no sources are relevant to this query.\n"
        "Do not include any text outside the JSON."
    )

    llm = get_llm(temperature=0.0, purpose="general")
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
    except (RateLimitError, LLMProviderError):
        raise
    except Exception as exc:
        raise LLMProviderError("LLM", str(exc)[:200]) from exc
    raw = str(response.content).strip()

    # Strip markdown fences if the model wraps the JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
        return {
            "file_ids": [str(i) for i in parsed.get("file_ids", [])],
            "source_ids": [str(i) for i in parsed.get("source_ids", [])],
            "reason": str(parsed.get("reason", "")),
        }
    except Exception:
        logger.warning(
            "data_agent: select_relevant_sources parse error — raw=%r, falling back to all sources",
            raw[:300],
        )
        # Fall back to all available sources so the query can still run.
        return {
            "file_ids": [f["file_id"] for f in data_files],
            "source_ids": [c["id"] for c in data_connections],
            "reason": "parse_error_fallback_all",
        }


async def generate_duckdb_sql(
    user_query: str,
    selected_schemas: list[dict],
    conversation_history: list[dict],
) -> str:
    """Ask Gemini to write a DuckDB SQL query for the given schemas and question.

    selected_schemas shape: [{source_name, source_type, columns: [{name, type}]}]
    Returns a plain SQL string (no markdown fences).
    """
    schema_context = "\n".join(
        "Source '{}' ({}):\n  Columns: {}".format(
            s["source_name"],
            s["source_type"],
            ", ".join(f"{c['name']}({c['type']})" for c in s["columns"]) or "(unknown)",
        )
        for s in selected_schemas
    )

    recent = conversation_history[-3:]
    history_context = "\n".join(
        f"{m['role'].capitalize()}: {m['content'][:200]}" for m in recent
    ) or "(none)"

    prompt = (
        "You are a DuckDB SQL expert. Generate a SQL query to answer the user's question.\n\n"
        f"Available data sources and their schemas:\n{schema_context}\n\n"
        f"Recent conversation:\n{history_context}\n\n"
        f"User question: {user_query}\n\n"
        "Rules you MUST follow:\n"
        "1. Use DuckDB SQL syntax only\n"
        "2. For data files, reference them by filename: read_auto('{filename}')\n"
        "3. For database connections, use the table names directly\n"
        "4. ALWAYS prefer aggregations (GROUP BY, SUM, COUNT, AVG, MIN, MAX) over row-level queries\n"
        "5. ALWAYS add LIMIT 500 to any SELECT that is not fully aggregated\n"
        "6. NEVER use: DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, TRUNCATE, EXECUTE, COPY\n"
        "7. If multiple sources needed, generate separate queries (one per source)\n\n"
        "Return ONLY the SQL query, no explanation, no markdown code blocks."
    )

    llm = get_sql_llm()
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
    except (RateLimitError, LLMProviderError):
        raise
    except Exception as exc:
        raise LLMProviderError("LLM", str(exc)[:200]) from exc
    sql = str(response.content).strip()

    # Strip markdown fences
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql.strip())
    return sql.strip()


def validate_sql(sql: str) -> tuple[bool, str]:
    """Return (True, '') if the SQL is safe, or (False, reason) if forbidden patterns found."""
    if len(sql) > 3000:
        return False, "Generated SQL exceeds maximum length"

    sql_lower = sql.lower()
    for keyword in _FORBIDDEN_KEYWORDS:
        if keyword in _WORD_BOUNDARY_KEYWORDS:
            if re.search(r"\b" + re.escape(keyword) + r"\b", sql_lower):
                return False, f"SQL contains forbidden operation: '{keyword}'"
        else:
            if keyword in sql_lower:
                return False, f"SQL contains forbidden operation: '{keyword}'"

    if re.search(r";\s*(select|insert|update|delete|drop|create)", sql_lower):
        return False, "SQL contains multiple statements"

    return True, ""


async def run_data_analysis(
    db: AsyncSession,
    user_id: UUID,
    user_query: str,
    conversation_history: list[dict],
) -> dict:
    """
    Orchestrate source selection → SQL generation → validation → execution.

    Returns a result dict with keys: sql, columns, rows, row_count, total_row_count,
    truncated, summary_stats, sources_used.
    On failure returns {"error": str, "message": str}.
    """
    loop = asyncio.get_running_loop()

    # Load available sources
    data_files = await data_file_service.get_file_schemas_for_routing(db, user_id)
    raw_connections = await data_source_service.list_data_sources(db, user_id)

    connections: list[dict] = []
    for c in raw_connections:
        schema_summary: str | None = None
        if c.schema_cache:
            try:
                sc = json.loads(c.schema_cache)
                if "tables" in sc:
                    tables = sc["tables"]
                    schema_summary = f"{len(tables)} tables: {', '.join(tables[:5])}"
                elif "sample_files" in sc:
                    schema_summary = f"{sc.get('file_count', '?')} files"
            except Exception:
                pass
        connections.append(
            {
                "id": str(c.id),
                "name": c.name,
                "source_type": c.source_type,
                "schema_summary": schema_summary,
            }
        )

    if not data_files and not connections:
        return {
            "error": "no_sources",
            "message": (
                "No data files or connections found. "
                "Upload a file or add a connection in Data Sources."
            ),
        }

    # Let the LLM pick relevant sources
    selection = await select_relevant_sources(user_query, data_files, connections)
    file_ids = selection.get("file_ids", [])
    source_ids = selection.get("source_ids", [])

    if not file_ids and not source_ids:
        return {
            "error": "not_relevant",
            "message": "I couldn't find relevant data for this query in your connected sources.",
        }

    # Build schemas for SQL generation
    selected_schemas: list[dict] = []
    selected_file_map: dict[str, dict] = {}
    selected_source_map: dict[str, dict] = {}

    for f in data_files:
        if f["file_id"] in file_ids:
            selected_schemas.append(
                {"source_name": f["filename"], "source_type": "file", "columns": f["columns"]}
            )
            selected_file_map[f["file_id"]] = f

    for c in connections:
        if c["id"] in source_ids:
            selected_schemas.append(
                {"source_name": c["name"], "source_type": c["source_type"], "columns": []}
            )
            selected_source_map[c["id"]] = c

    # Generate SQL
    sql = await generate_duckdb_sql(user_query, selected_schemas, conversation_history)
    logger.info("Generated SQL for user %s: %s", user_id, sql[:100])

    # Validate SQL before execution
    valid, reason = validate_sql(sql)
    if not valid:
        return {"error": "sql_invalid", "message": f"Could not generate a safe query: {reason}"}

    # Execute queries and combine results
    all_columns: list[str] = []
    all_rows: list[list] = []
    total_rows_before_truncation = 0
    any_truncated = False
    all_summary_stats: dict = {}
    sources_used: list[dict] = []

    for file_id in selected_file_map:
        try:
            db_result = await db.execute(
                sa.select(DataFile).where(
                    DataFile.id == UUID(file_id),
                    DataFile.user_id == user_id,
                    DataFile.deleted_at.is_(None),
                )
            )
            data_file_obj = db_result.scalar_one_or_none()
            if data_file_obj is None:
                logger.warning(
                    "data_agent: file_id %s not found or not owned by user %s — skipping",
                    file_id,
                    user_id,
                )
                continue

            file_bytes = data_file_obj.file_data
            filename = data_file_obj.filename

            query_result = await loop.run_in_executor(
                None,
                lambda fb=file_bytes, fn=filename: duckdb_service.query_file(
                    fb, fn, sql, user_id=user_id
                ),
            )

            if not all_columns:
                all_columns = query_result["columns"]
                all_rows = list(query_result["rows"])
            elif query_result["columns"] == all_columns:
                all_rows.extend(query_result["rows"])
            else:
                # Column mismatch — keep primary result; log and note for synthesis.
                logger.warning(
                    "data_agent: column mismatch for file_id=%s (%s vs %s) — skipping merge",
                    file_id,
                    query_result["columns"],
                    all_columns,
                )

            total_rows_before_truncation += query_result["total_row_count"]
            if query_result["truncated"]:
                any_truncated = True
            all_summary_stats.update(query_result["summary_stats"])
            sources_used.append({"name": filename, "type": "file"})

        except Exception as exc:
            logger.error("data_agent: query_file failed for file_id=%s: %s", file_id, exc)
            return {"error": "query_failed", "message": f"Query execution failed: {exc}"}

    for source_id in selected_source_map:
        try:
            ds = await data_source_service.get_data_source(db, user_id, UUID(source_id))
            config = data_source_service.get_decrypted_config(ds)
            source_type = ds.source_type
            source_name = ds.name

            query_result = await loop.run_in_executor(
                None,
                lambda cfg=config, st=source_type, sn=source_name: duckdb_service.query_data_source(
                    cfg, st, sql, source_name=sn, user_id=user_id
                ),
            )

            if not all_columns:
                all_columns = query_result["columns"]
                all_rows = list(query_result["rows"])
            elif query_result["columns"] == all_columns:
                all_rows.extend(query_result["rows"])
            else:
                logger.warning(
                    "data_agent: column mismatch for source_id=%s (%s vs %s) — skipping merge",
                    source_id,
                    query_result["columns"],
                    all_columns,
                )

            total_rows_before_truncation += query_result["total_row_count"]
            if query_result["truncated"]:
                any_truncated = True
            all_summary_stats.update(query_result["summary_stats"])
            sources_used.append({"name": source_name, "type": source_type})

        except Exception as exc:
            logger.error(
                "data_agent: query_data_source failed for source_id=%s: %s", source_id, exc
            )
            return {"error": "query_failed", "message": f"Query execution failed: {exc}"}

    row_count = len(all_rows)
    logger.info(
        "Data analysis complete — user %s: %d rows, sources: %s",
        user_id,
        row_count,
        [s["name"] for s in sources_used],
    )

    return {
        "sql": sql,
        "columns": all_columns,
        "rows": all_rows,
        "row_count": row_count,
        "total_row_count": total_rows_before_truncation,
        "truncated": any_truncated,
        "summary_stats": all_summary_stats,
        "sources_used": sources_used,
    }
