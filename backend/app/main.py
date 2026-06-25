"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.auth import router as auth_router
from app.api.chat import messages_router as chat_messages_router
from app.api.chat import threads_router as chat_threads_router
from app.api.data_files import router as data_files_router
from app.api.data_sources import router as data_sources_router
from app.api.documents import router as documents_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import AsyncSessionLocal
from app.services import duckdb_service

# ── Structured logging ────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Startup: clean up any orphaned DuckDB temp files left by a previous crash."""
    try:
        duckdb_service.cleanup_orphaned_temp_files()
        logger.info("Startup: orphaned DuckDB temp files cleaned")
    except Exception:
        logger.exception("Startup: temp file cleanup failed (non-fatal)")
    yield


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="RAG Application",
    description="Retrieval-Augmented Generation API",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter — state.limiter must be set before any request is processed.
app.state.limiter = limiter

# Browser → backend direct calls with credentials: 'include'.
# allow_credentials=True is required for cookies (httpOnly auth cookies) to be sent and received.
# Wildcard origins ("*") are incompatible with allow_credentials, so origins come from settings.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Cookie"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chat_threads_router)
app.include_router(chat_messages_router)
app.include_router(documents_router)
app.include_router(data_sources_router)
app.include_router(data_files_router)


# ── Middleware ────────────────────────────────────────────────────────────────


@app.middleware("http")
async def add_security_headers(request: Request, call_next):  # type: ignore[type-arg]
    """Attach security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    if settings.ENVIRONMENT == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "font-src 'self'"
        )
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[type-arg]
    """Log every request at INFO level with the final status code."""
    response = await call_next(request)
    logger.info("%s %s → %d", request.method, request.url.path, response.status_code)
    return response


# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a structured 429 response with Retry-After header."""
    retry_after = 60
    try:
        # SlowAPI exposes the limit's reset window via exc.limit.get_expiry()
        retry_after = int(exc.limit.get_expiry())  # type: ignore[attr-defined]
    except Exception:
        pass
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            "type": "rate_limit_exceeded",
        },
        headers={"Retry-After": str(retry_after)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled (non-HTTP) exceptions.

    Without this, Starlette's ServerErrorMiddleware returns plain-text
    'Internal Server Error' for any exception that isn't an HTTPException.
    That plain-text body causes every caller that does response.json() to
    throw 'Unexpected end of JSON input' instead of surfacing the real error.

    HTTPException and RequestValidationError are handled by FastAPI's own
    handlers before they reach here, so they are unaffected.
    """
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "type": "internal_error",
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    """
    Liveness + readiness probe.

    Returns 200 with database=connected when healthy, 503 when the DB is unreachable.
    """
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(sa.text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.exception("Health check: database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unreachable", "version": "1.0.0"},
        )
    return JSONResponse(
        content={"status": "healthy", "database": db_status, "version": "1.0.0"}
    )
