# Backend

FastAPI backend for the RAG application. Handles authentication, chat threads, document processing, data analysis, and the LangGraph agent pipeline.

## Architecture

```
app/
├── api/          Routes (thin — delegate to services)
├── agents/       LangGraph pipeline
├── core/         Config, security, rate limiting, encryption
├── db/           SQLAlchemy engine and session
├── models/       ORM models
├── schemas/      Pydantic request/response schemas
├── services/     Business logic
└── main.py       FastAPI entrypoint
```

The `api/` layer only validates inputs and calls `services/`. Business logic lives entirely in `services/`. The `agents/` package is called by the chat API when a message is sent and has no knowledge of HTTP.

## API Endpoints

All routes are prefixed with `/api`. No `/v1` version prefix. Interactive docs at **http://localhost:8000/docs**.

### Auth — `/api/auth/...`

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/signup` | Register a new account. If `REQUIRE_EMAIL_VERIFICATION=true`, sends a verification email and returns a message. If `false`, marks the user verified immediately. |
| POST | `/api/auth/verify-email?token=...` | Verify email with the token from the verification email. Sets auth cookies and returns `UserResponse`. |
| POST | `/api/auth/resend-verification` | Resend the verification email. Rate-limited to 2 requests/hour. Always returns a generic message (prevents email enumeration). |
| POST | `/api/auth/login` | Authenticate with email + password. Returns `UserResponse` and sets httpOnly auth cookies. Returns 403 if the account is unverified. |
| POST | `/api/auth/refresh` | Exchange the `refresh_token` cookie for a new rotated token pair. Old refresh token is revoked in the DB. |
| POST | `/api/auth/logout` | Revoke the current refresh token and clear both auth cookies. |
| POST | `/api/auth/forgot-password` | Generate a password reset token and send it via Resend. Returns `debug_reset_link` in the response body when `ENVIRONMENT=local`. |
| POST | `/api/auth/reset-password` | Validate the reset token and update the password. Token expires after 1 hour. |

### Users — `/api/users/...`

| Method | Path | Description |
|---|---|---|
| GET | `/api/users/me` | Return the current user's profile. |
| PATCH | `/api/users/me` | Update the user's display name. |
| PATCH | `/api/users/me/password` | Change password. Requires current password. Validates strength (8+ chars, upper, lower, digit). |
| POST | `/api/users/me/avatar` | Upload a profile picture (JPEG/PNG/WebP, max 5 MB). Stored as `bytea` in Postgres. Magic-byte validated. |
| GET | `/api/users/me/avatar` | Serve the user's avatar image with the correct `Content-Type`. Returns 404 if no avatar set. |
| GET | `/api/users/me/stats` | Return aggregate usage stats: document count, total chunks, responses generated, total input tokens, total output tokens. |
| DELETE | `/api/users/me` | Permanently delete the account and all data. Requires current password. Deletion order: refresh_tokens → document_chunks → documents → chat_messages → chat_threads → user. |

### Chat Threads — `/api/chat-threads/...`

| Method | Path | Description |
|---|---|---|
| GET | `/api/chat-threads` | List all non-deleted threads for the current user, newest first. Paginated. |
| POST | `/api/chat-threads` | Create a new thread with a provided title. |
| PATCH | `/api/chat-threads/{thread_id}` | Rename a thread. |
| PATCH | `/api/chat-threads/{thread_id}/pin` | Toggle the pinned state of a thread. Returns the updated thread. Pinned threads appear in a separate section and cannot be deleted. |
| DELETE | `/api/chat-threads/{thread_id}` | Soft-delete a single thread (sets `deleted_at`). Returns 400 if the thread is pinned. |
| DELETE | `/api/chat-threads` | Soft-delete all non-pinned threads and hard-delete their messages. Body: `{ "password": "..." }`. Returns `{ "deleted_count": N }`. |
| GET | `/api/chat-threads/{thread_id}/messages` | List messages in a thread. Paginated, oldest first. |
| POST | `/api/chat-threads/{thread_id}/messages` | Send a user message and run the LangGraph agent synchronously. Returns both the saved user message and the assistant response. Auto-generates thread title after the first message. |
| POST | `/api/chat-threads/{thread_id}/messages/stream` | Send a user message and stream the LangGraph agent response as Server-Sent Events. See [Streaming](#streaming) below. |

### Chat Messages — `/api/chat-messages/...`

| Method | Path | Description |
|---|---|---|
| PATCH | `/api/chat-messages/{message_id}` | Edit a user message and regenerate the assistant response. Subsequent messages in the thread are replaced. |
| POST | `/api/chat-messages/{message_id}/regenerate` | Re-run the agent on an existing user message to get a new assistant response. |

### Documents — `/api/documents/...`

| Method | Path | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload a document (multipart/form-data, max 20 MB). Returns 202 immediately; processing runs in a `BackgroundTask`. Invalidates the `doc_count:{user_id}` Redis cache on success. |
| GET | `/api/documents` | List the current user's non-deleted documents with chunk counts. Paginated. |
| GET | `/api/documents/{document_id}/status` | Poll processing status: `processing`, `ready`, or `failed`. |
| DELETE | `/api/documents/{document_id}` | Soft-delete the document and immediately hard-delete all its chunks (prevents stale RAG results). Invalidates the `doc_count:{user_id}` Redis cache. |

### Data Files — `/api/data-files/...`

| Method | Path | Description |
|---|---|---|
| POST | `/api/data-files/upload` | Upload a data file (CSV, TSV, Excel, Parquet, JSON — max 20 MB). Returns 202 immediately; schema extraction runs in a `BackgroundTask`. Rate-limited to 20 uploads/minute. |
| GET | `/api/data-files` | List the current user's data files with schema columns. |
| GET | `/api/data-files/{id}/schema` | Full schema including column types, sample values, and row count. |
| GET | `/api/data-files/{id}/status` | Lightweight status poll: `processing`, `ready`, or `failed`. |
| DELETE | `/api/data-files/{id}` | Soft-delete the file and hard-delete schema rows. Invalidates all `duckdb:{file_id}:*` Redis cache entries. |

### Data Sources — `/api/data-sources/...`

| Method | Path | Description |
|---|---|---|
| GET | `/api/data-sources` | List all data source connections (never includes credentials). |
| POST | `/api/data-sources` | Create a new connection. Config validated per `source_type`, then Fernet-encrypted at rest. |
| GET | `/api/data-sources/{id}` | Get connection details with cached schema. |
| PATCH | `/api/data-sources/{id}` | Update name and/or connection config. |
| DELETE | `/api/data-sources/{id}` | Hard-delete the connection. |
| POST | `/api/data-sources/{id}/test` | Test connectivity. Rate-limited to 10/minute. |

### System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + readiness probe. Returns `{"status":"healthy","database":"connected","version":"1.0.0"}` or 503 if the database is unreachable. |

## Streaming

`POST /api/chat-threads/{thread_id}/messages/stream` returns a `text/event-stream` response. Each event is a `data: <json>\n\n` line. Event shapes:

```
{"type": "status",  "content": "🤔 Thinking…"}
{"type": "token",   "content": "<partial LLM token>"}
{"type": "done",    "user_message": {...}, "assistant_message": {...}, "thread": {...}}
{"type": "error",   "content": "<error message>"}
```

- `status` — emitted at the start of each agent node (Thinking, Searching documents, Searching web, Analysing data, Writing response)
- `token` — individual LLM output token from the synthesis node, enabling character-by-character streaming in the UI
- `done` — emitted after the assistant message is saved to the database; includes full user and assistant message objects. `assistant_message.data_analysis_result` is populated for data analysis queries.
- `error` — emitted if the agent raises an unhandled exception

The nginx reverse proxy sets `proxy_buffering off` on the SSE location block so tokens reach the browser immediately without buffering.

## Service Layer

Each service file has a single responsibility:

**`auth_service.py`** — Cryptography and token lifecycle. `hash_password` / `verify_password` (bcrypt). `create_access_token` / `create_refresh_token` (JWT). `store_refresh_token` (saves SHA-256 hash), `get_valid_refresh_token`, `revoke_refresh_token`. `generate_reset_token` / `reset_token_expiry`.

**`cache.py`** — Async Redis wrapper. Client initialised lazily on first use; any connection failure silently returns `None` (cache miss) so the app never crashes on Redis unavailability. Public functions: `get_cached(key)`, `set_cached(key, val, ttl)`, `delete_cached(key)`, `delete_pattern(pattern)` (uses `SCAN` + `DEL` for prefix-based invalidation), `cache_key(prefix, *parts)` (first part kept literal for pattern-matching; remaining parts hashed with MD5 to bound key length).

**`user_service.py`** — User CRUD. `get_user_by_email`, `get_user_by_id`, `get_user_by_reset_token`, `get_user_by_verification_token`. `create_user`, `update_user_*` (name, avatar, password, reset_token, verification_token). `mark_user_verified`. `get_user_stats` (aggregates documents, chunks, assistant messages, and token sums). `delete_user` (FK-safe cascade delete).

**`chat_service.py`** — Thread and message CRUD. `list_threads` / `list_threads_paginated`. `get_thread` (ownership check + soft-delete filter). `create_thread`, `rename_thread`, `pin_thread`, `delete_thread` (soft). `delete_all_non_pinned_threads` (soft-deletes threads, hard-deletes their messages, skips pinned). `list_messages`, `create_message`, `get_message`, `update_message`, `delete_messages_after`. `create_assistant_message(db, thread_id, user_id, content, sources, input_tokens, output_tokens, data_analysis_result)`. `replace_assistant_message`.

**`document_service.py`** — Full document pipeline. `validate_file` (magic bytes, format allow-list). `extract_text` (dispatch per format: PyMuPDF for PDF, python-docx for DOCX, openpyxl for XLSX, csv for CSV, plain read for TXT/MD/JSON). `chunk_text` (2000-char chunks, 400 overlap). `save_document`. `process_document` (background: extract → chunk → embed → insert chunks). `list_documents_paginated`, `get_document_status`. `delete_document` (soft-delete document, hard-delete chunks).

**`duckdb_service.py`** — SQL execution over uploaded files. `get_file_schema(file_bytes, filename)` — returns column names, types, sample values, and row count. `query_file(file_bytes, filename, sql, user_id)` — synchronous; writes file to `/tmp/duckdb_work/` with a UUID prefix (`chmod 0o600`), executes SQL with a 30-second timeout, returns `{columns, rows, row_count, total_row_count, truncated, sql}`. Max 500 rows returned. `query_file_cached(file_bytes, filename, sql, file_id, user_id)` — async wrapper; key `duckdb:{file_id}:{MD5(_normalise_sql(sql))}`, TTL 600 s. `_normalise_sql(sql)` collapses whitespace and lowercases for cache-key stability; original SQL is passed to DuckDB unchanged.

**`data_file_service.py`** — File upload, schema extraction, routing. `upload_data_file` (validates type + size, stores raw bytes, triggers background schema extraction). `extract_and_store_schema` (background: calls `get_file_schema`, stores column metadata). `list_data_files`, `get_data_file`, `delete_data_file`.

**`data_source_service.py`** — External database connection management. `create_data_source`, `list_data_sources`, `get_data_source`, `update_data_source`, `delete_data_source`. `get_decrypted_config` — the only place credentials are decrypted (Fernet). `test_connection`. `_assert_no_credentials()` verifies at runtime that no credential keys appear in serialised API responses.

**`email_service.py`** — Resend API via `asyncio.to_thread`. `send_verification_email`, `send_password_reset_email`. Both use inline HTML templates with CTA buttons. Links point to `FRONTEND_URL` from config.

**`llm_service.py`** — `LLMProvider` Protocol (structural typing). `GeminiProvider` implements it with two `ChatGoogleGenerativeAI` clients (temperature 0.7 for chat, 0.3 for title generation). `get_llm_provider()` singleton via `@lru_cache`.

**`embedding_service.py`** — `EmbeddingProvider` Protocol. `GeminiEmbeddingProvider` wraps `gemini-embedding-001` for 768-dimensional embeddings. `embed_query` / `embed_documents`. `get_embedding_provider()` singleton.

**`retrieval_service.py`** — `count_ready_documents(db, user_id) → int` (scalar count used by `router_node` for caching). `has_ready_documents(db, user_id) → bool` (delegates to `count_ready_documents`). `similarity_search(db, user_id, query_embedding, top_k=5)` — pgvector cosine distance, always scoped to `user_id`, returns `[{text, filename, distance}]`.

## Agent Architecture

The LangGraph agent lives in `app/agents/`. It is a compiled `StateGraph` with five nodes:

```
router_node
     │
     ├── route == "llm_only"       ──────────────────────────────► synthesis_node
     ├── route == "retrieval"      ──► retrieval_node   ─────────► synthesis_node
     ├── route == "web_search"     ──► websearch_node   ─────────► synthesis_node
     ├── route == "both"           ──► retrieval_node ─┐
     │                                  websearch_node ─┘─────────► synthesis_node
     └── route == "data_analysis"  ──► data_analysis_node ────────► synthesis_node
```

**`router_node`** — Reads the document count from Redis (`doc_count:{user_id}`, TTL 60 s). On cache miss, calls `count_ready_documents(db, user_id)` and caches the result. Calls Gemini (temperature 0) with a routing prompt that produces one of `{llm_only, retrieval, web_search, both, data_analysis}`. Falls back to `retrieval` (if has docs) or `llm_only` (if not) on invalid LLM output.

**`retrieval_node`** — Embeds the user query via `GeminiEmbeddingProvider`, runs `similarity_search` (top 5 chunks) against the user's `document_chunks`.

**`websearch_node`** — Calls `AsyncTavilyClient.search(query, max_results=5)`. Returns `[{title, url, content}]`. Swallows exceptions and returns empty list on failure.

**`data_analysis_node`** — Calls `data_agent_node.run_data_analysis(db, user_id, query, conversation_history)`. Internally: selects relevant data sources/files (LLM-assisted), generates DuckDB SQL (LLM), validates SQL (blocks DML keywords, dangerous prefixes, SQL > 3000 chars), retrieves file bytes from Postgres, calls `query_file_cached` (Redis-backed), and returns `DataAnalysisResult` stored in `state["data_analysis_result"]`.

**`synthesis_node`** — Builds a context block from retrieved chunks and/or web results. For data analysis queries, includes the actual query result as a pipe-separated table (up to 50 rows) followed by a strict 2-sentence insight instruction: the LLM must state the single most important finding with one specific number, then a pattern or business implication — no row repetition, no preamble. Calls Gemini (temperature 0.7) via `astream()`. Captures `usage_metadata` from the last streaming chunk to record `input_tokens` and `output_tokens`.

### Public entrypoints in `graph.py`

**`run_agent(db, user_id, messages) → tuple[str, str, int, int, dict | None]`** — Invokes the graph synchronously and returns `(answer, sources, input_tokens, output_tokens, data_analysis_result)`.

**`stream_agent_events(db, user_id, messages) → AsyncIterator[dict]`** — Runs the graph via `astream_events` and yields dicts for the SSE endpoint: `status` events on node start, `token` events during synthesis, and a `final` event on completion carrying `answer`, `sources`, `input_tokens`, `output_tokens`, `data_analysis_result`.

The graph is compiled once at import time and reused across all requests. The `db` session and `user_id` are passed via `config["configurable"]` to keep them out of serialisable state.

## Database Schema

Tables managed exclusively by Alembic:

**`users`** — id (UUID PK), name, email (unique), hashed_password, profile_picture_data (bytea nullable), profile_picture_content_type, is_verified (bool), email_verification_token, email_verification_expires_at, reset_token, reset_token_expires_at, created_at, updated_at

**`refresh_tokens`** — id (UUID PK), user_id (FK→users CASCADE), token_hash (SHA-256, unique), expires_at, revoked (bool), created_at

**`chat_threads`** — id (UUID PK), user_id (FK→users), title, pinned (bool default false), created_at, updated_at, deleted_at (nullable — soft delete)

**`chat_messages`** — id (UUID PK), thread_id (FK→chat_threads), user_id (FK→users), role ('user'|'assistant'), content, sources (nullable, String(20)), data_analysis_result (JSON nullable), input_tokens (int default 0), output_tokens (int default 0), created_at, edited_at (nullable)

**`documents`** — id (UUID PK), user_id (FK→users), filename, file_data (bytea), content_type, status ('processing'|'ready'|'failed'), processing_error (nullable), uploaded_at, deleted_at (nullable — soft delete)

**`document_chunks`** — id (UUID PK), document_id (FK→documents CASCADE), user_id (FK→users), chunk_text, embedding (vector(768)), chunk_index, created_at

**`data_files`** — id (UUID PK), user_id (FK→users), filename, file_data (bytea), content_type, file_size, status ('processing'|'ready'|'failed'), processing_error (nullable), uploaded_at, deleted_at (nullable)

**`data_file_schemas`** — id (UUID PK), data_file_id (FK→data_files CASCADE), user_id (FK→users), column_name, column_type, sample_values (JSON), row_count, created_at

**`data_sources`** — id (UUID PK), user_id (FK→users), name, source_type ('postgresql'|'mysql'|'sqlite'|'s3'|'gcs'|'azure_blob'|'rest_api'), connection_config (Fernet-encrypted text), schema_cache (JSON nullable), created_at, updated_at

All user-owned tables have an indexed `user_id` column. All service-layer queries filter by `user_id`.

## Redis Caching

Two cache key namespaces:

**`duckdb:{file_id}:{MD5(normalised_sql)}`** — DuckDB query result (TTL 600 s). SQL is normalised (whitespace collapsed, lowercased) for the key only; the original SQL is executed by DuckDB. Invalidated by `delete_pattern(f"duckdb:{file_id}:*")` when a data file is deleted. Written and read by `duckdb_service.query_file_cached()`.

**`doc_count:{user_id}`** — Count of `ready` document chunks for a user (TTL 60 s). Used by `router_node` to decide whether the `retrieval` route is available without hitting Postgres on every message. Invalidated by `delete_cached(f"doc_count:{user_id}")` in `documents.py` after every successful upload and delete.

If Redis is unavailable, all cache operations silently return `None` (cache miss) — the app continues to function normally, just without caching.

## Alembic Migrations

```
1. 0001_initial_schema              — pgvector extension, all core tables
2. 717d7488b704                     — document processing status and error fields
3. c7a8f9b0e1d2                     — sources field on chat_messages
4. d8e9f0a1b2c3                     — profile picture (bytea + content_type) on users
5. e1f2a3b4c5d6                     — refresh_tokens table
6. f2a3b4c5d6e7                     — email verification fields; soft-delete on threads and documents
7. g3h4i5j6k7l8                     — pinned column on chat_threads
8. h4i5j6k7l8m9                     — input_tokens and output_tokens on chat_messages
```

`entrypoint.sh` runs `alembic upgrade head` automatically on every container start. Never call `Base.metadata.create_all()` — Alembic is the only mechanism for schema changes.

## Running Locally

```bash
cd backend

# Create venv (once)
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS / Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start Postgres and Redis via Docker (if not running locally)
docker compose up -d postgres redis

# Set in .env:
#   POSTGRES_HOST=localhost
#   REDIS_URL=redis://localhost:6379

# Run migrations
alembic upgrade head

# Start with hot reload
uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

## Adding New Migrations

After modifying an ORM model in `app/models/`:

```bash
# With venv activated and POSTGRES_HOST=localhost
alembic revision --autogenerate -m "brief description of change"
# Review the generated file in alembic/versions/
alembic upgrade head
```

The `document_chunks` table is excluded from autogenerate (the `vector(768)` column type is not natively understood by Alembic). Changes to that table require a hand-written migration.

## Adding a New API Endpoint

1. Add route handler to the appropriate file in `app/api/`.
2. Add business logic to the appropriate service in `app/services/`.
3. Add request/response schema to `app/schemas/`.
4. If schema changes are needed, create an Alembic migration.
5. Route handler must:
   - Use `Depends(get_current_user)` for auth
   - Use `Depends(get_db)` for the DB session
   - Call a service function — no SQL in the route layer
   - Filter by `user_id` for any user-owned data
   - Invalidate relevant Redis cache keys if the endpoint mutates cached data

## Swapping the LLM Provider

`LLMProvider` in `llm_service.py` is a structural Protocol. To switch from Gemini:

1. Implement a new class with `async def chat(...)` and `async def generate_title(...)`.
2. Update `get_llm_provider()` to return the new instance.
3. No changes needed anywhere else in the codebase.

The same pattern applies for `EmbeddingProvider` in `embedding_service.py`.
