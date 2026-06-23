# Backend

FastAPI backend for the RAG application. Handles authentication, chat threads, document processing, and the LangGraph agent pipeline.

## Architecture

```
app/
├── api/          Routes (thin — delegate to services)
├── agents/       LangGraph pipeline
├── core/         Config, security, rate limiting
├── db/           SQLAlchemy engine and session
├── models/       ORM models
├── schemas/      Pydantic request/response schemas
├── services/     Business logic
└── main.py       FastAPI entrypoint
```

The `api/` layer only validates inputs and calls `services/`. Business logic lives entirely in `services/`. The `agents/` package is called by `chat_service` when a message is sent and has no knowledge of HTTP.

## API Endpoints

All routes are prefixed with `/api`. No `/v1` version prefix. Interactive docs at **http://localhost:8000/docs**.

### Auth — `POST /api/auth/...`

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
| DELETE | `/api/users/me` | Permanently delete the account and all data. Requires current password. Deletion order: refresh_tokens → document_chunks → documents → chat_messages → chat_threads → user. |

### Chat Threads — `/api/chat-threads/...`

| Method | Path | Description |
|---|---|---|
| GET | `/api/chat-threads` | List all threads for the current user, newest first. Paginated. Excludes soft-deleted threads. |
| POST | `/api/chat-threads` | Create a new thread with a provided title. |
| PATCH | `/api/chat-threads/{thread_id}` | Rename a thread. |
| DELETE | `/api/chat-threads/{thread_id}` | Soft-delete a thread (sets `deleted_at`). Thread and messages are not physically removed. |
| GET | `/api/chat-threads/{thread_id}/messages` | List messages in a thread. Paginated, oldest first. |
| POST | `/api/chat-threads/{thread_id}/messages` | Send a user message and run the LangGraph agent. Returns both the saved user message and the assistant response. Auto-generates thread title after the first message. |

### Chat Messages — `/api/chat-messages/...`

| Method | Path | Description |
|---|---|---|
| PATCH | `/api/chat-messages/{message_id}` | Edit a user message and regenerate the assistant response. Subsequent messages in the thread are replaced. |
| POST | `/api/chat-messages/{message_id}/regenerate` | Re-run the agent on an existing user message to get a new assistant response. |

### Documents — `/api/documents/...`

| Method | Path | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload a document (multipart/form-data). Returns 202 immediately; processing runs in a `BackgroundTask`. |
| GET | `/api/documents` | List the current user's non-deleted documents with chunk counts. Paginated. |
| GET | `/api/documents/{document_id}/status` | Poll processing status: `processing`, `ready`, or `failed`. |
| DELETE | `/api/documents/{document_id}` | Soft-delete the document and immediately hard-delete all its chunks (prevents stale RAG results). |

### System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + readiness probe. Returns `{"status":"healthy","database":"connected","version":"1.0.0"}` or 503 if the database is unreachable. |

## Service Layer

Each service file has a single responsibility:

**`auth_service.py`** — Cryptography and token lifecycle. `hash_password` / `verify_password` (bcrypt). `create_access_token` / `create_refresh_token` (JWT). `store_refresh_token` (saves SHA-256 hash), `get_valid_refresh_token`, `revoke_refresh_token`. `generate_reset_token` / `reset_token_expiry`.

**`user_service.py`** — User CRUD. `get_user_by_email`, `get_user_by_id`, `get_user_by_reset_token`, `get_user_by_verification_token`. `create_user`, `update_user_*` (name, avatar, password, reset_token, verification_token). `mark_user_verified`. `delete_user` (FK-safe cascade delete).

**`chat_service.py`** — Thread and message CRUD. `list_threads` / `list_threads_paginated`. `get_thread` (ownership check + soft-delete filter). `create_thread`, `rename_thread`, `delete_thread` (soft). `list_messages`, `create_message`, `get_message`, `update_message`, `delete_messages_after`. `replace_assistant_message`, `count_thread_messages`, `list_messages_before`, `list_messages_paginated`.

**`document_service.py`** — Full document pipeline. `validate_file` (magic bytes, format allow-list). `extract_text` (dispatch per format: PyMuPDF for PDF, python-docx for DOCX, openpyxl for XLSX, csv for CSV, plain read for TXT/MD/JSON). `chunk_text` (2000-char chunks, 400 overlap via `RecursiveCharacterTextSplitter`). `save_document` (stores raw bytes). `process_document` (background: extract → chunk → embed → insert chunks). `list_documents`, `list_documents_paginated`, `get_document`, `get_document_status`. `delete_document` (soft-delete document, hard-delete chunks).

**`email_service.py`** — Resend API via `asyncio.to_thread`. `send_verification_email`, `send_password_reset_email`. Both use inline HTML templates with CTA buttons.

**`llm_service.py`** — `LLMProvider` Protocol (structural typing). `GeminiProvider` implements it with two `ChatGoogleGenerativeAI` clients (temperature 0.7 for chat, 0.3 for title generation). `get_llm_provider()` singleton via `@lru_cache`.

**`embedding_service.py`** — `EmbeddingProvider` Protocol. `GeminiEmbeddingProvider` wraps `gemini-embedding-001` for 768-dimensional embeddings. `embed_query` / `embed_documents`. `get_embedding_provider()` singleton.

**`retrieval_service.py`** — `has_ready_documents(db, user_id)`. `similarity_search(db, user_id, query_embedding, top_k=5)` — pgvector cosine distance, always scoped to `user_id`, returns `[{text, filename, distance}]`.

## Agent Architecture

The LangGraph agent lives in `app/agents/`. It is a compiled `StateGraph` with four nodes:

```
router_node
     │
     ├── route == "llm_only"   ──────────────────────► synthesis_node
     ├── route == "retrieval"  ──► retrieval_node ───► synthesis_node
     ├── route == "web_search" ──► websearch_node ───► synthesis_node
     └── route == "both"       ──► retrieval_node ─┐
                                   websearch_node ─┘► synthesis_node
```

**`router_node`** — Checks `has_ready_documents(db, user_id)`, then calls Gemini (temperature 0) with a routing prompt that produces one of `{llm_only, retrieval, web_search, both}`. Falls back to `retrieval` (if has docs) or `llm_only` (if not) on invalid output.

**`retrieval_node`** — Embeds the user query via `GeminiEmbeddingProvider`, runs `similarity_search` (top 5 chunks) against the user's `document_chunks`.

**`websearch_node`** — Calls `AsyncTavilyClient.search(query, max_results=5)`. Returns `[{title, url, content}]`. Swallows exceptions and returns empty list on failure.

**`synthesis_node`** — Builds a context block from retrieved chunks and/or web results. Prepends it as a `SystemMessage` to the full conversation history. Calls Gemini (temperature 0.7) to produce the final answer. Sets `sources` to `"llm_only"`, `"retrieval"`, `"web_search"`, or `"both"`.

The graph is compiled once at import time (`_build_graph()`) and reused. The `db` session and `user_id` are passed via `config["configurable"]` to keep them out of serialisable state.

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

# Ensure POSTGRES_HOST=localhost in .env
# Ensure Postgres is running locally (or start just postgres via Docker)
docker compose up -d postgres

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

## Swapping the LLM Provider

`LLMProvider` in `llm_service.py` is a structural Protocol. To switch from Gemini:

1. Implement a new class with `async def chat(...)` and `async def generate_title(...)`.
2. Update `get_llm_provider()` to return the new instance.
3. No changes needed anywhere else in the codebase.

The same pattern applies for `EmbeddingProvider` in `embedding_service.py`.
