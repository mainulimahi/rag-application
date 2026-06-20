# RAG Application

A general-purpose Retrieval-Augmented Generation (RAG) system. Users upload documents; the system chunks, embeds, and stores them in PostgreSQL (pgvector). Questions are answered by an AI agent that routes dynamically between document retrieval and live web search.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLAlchemy (async) + PostgreSQL + pgvector |
| LLM / Embeddings | Gemini API (`gemini-2.5-flash`, `gemini-embedding-001`) |
| Agent | LangGraph (retrieval ↔ web search router) |
| Web search | Tavily API |
| Frontend | Next.js 14 (App Router, TypeScript strict) |
| Containers | Docker Compose (Docker Desktop) |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — runs all services
- Python 3.12+ — for local backend development and running migrations
- Node.js 20+ — for local frontend development

## Quick start (Docker Compose)

**1. Configure environment variables:**

```bash
cp .env.example .env
# Open .env and fill in all API keys and credentials
```

**2. Start all services:**

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Frontend | http://localhost:3000 |
| Postgres | localhost:5432 |

**3. Run database migrations** (once, after postgres is healthy):

```bash
docker compose exec backend alembic upgrade head
```

**4. Verify the API:**

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

## Local backend development (without Docker)

Use this when iterating on backend code against a locally running Postgres.

```bash
# 1. Create a virtual environment (do this once)
cd backend
python -m venv venv

# 2. Activate it
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set POSTGRES_HOST=localhost in .env (instead of "postgres")

# 5. Start the dev server
uvicorn app.main:app --reload
```

> Always activate the venv before running any Python commands in the backend directory.

## Running migrations

All schema changes go through Alembic. Never call `Base.metadata.create_all()` directly.

```bash
# Run from backend/ with venv activated (or via docker compose exec backend)

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Check current state
alembic current

# Show migration history
alembic history

# Generate a new migration after changing SQLAlchemy models
alembic revision --autogenerate -m "describe the change"
```

> **After pulling changes:** always run `alembic upgrade head` if new migration files are present.

## Local frontend development (without Docker)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Project structure

```
rag-application/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route definitions (versioned: /api/v1/)
│   │   ├── agents/       # LangGraph graph + nodes
│   │   ├── core/         # config.py (settings), security helpers
│   │   ├── db/           # SQLAlchemy engine, session factory, declarative base
│   │   ├── models/       # ORM models (user, chat_thread, chat_message, document, document_chunk)
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic (auth, chat, document, embedding, llm, retrieval, websearch)
│   │   └── main.py       # FastAPI entrypoint
│   ├── alembic/          # Migration environment + version files
│   ├── tests/
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js App Router pages and layouts
│   │   ├── components/   # Shared UI components
│   │   └── lib/          # API client, shared TypeScript types
│   ├── package.json
│   └── tsconfig.json     # strict: true
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

## Architecture notes

- **Data isolation:** every user-owned table (`documents`, `document_chunks`, `chat_threads`, `chat_messages`) has a `user_id` NOT NULL FK. All queries filter by `user_id` at the service layer — cross-user data access is impossible by design.
- **Document storage:** uploaded files are stored as `bytea` in Postgres — no local filesystem or S3 dependency.
- **Provider abstraction:** LLM and embedding calls go through service interfaces so Gemini can be swapped for another provider without touching calling code.
- **Migrations:** Alembic is the sole mechanism for schema changes. No auto-migration on startup.
- **Agentic routing:** the LangGraph agent in `agents/` decides per-query whether to use the vector retrieval tool, the Tavily web search tool, or both, then synthesizes the final answer.

## Environment variables

All configuration lives in the root `.env` file (gitignored). See `.env.example` for the full list with descriptions. Never commit real API keys.
