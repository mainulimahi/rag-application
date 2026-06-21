"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.chat import messages_router as chat_messages_router
from app.api.chat import threads_router as chat_threads_router
from app.api.documents import router as documents_router
from app.api.users import router as users_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Application",
    description="Retrieval-Augmented Generation API",
    version="0.1.0",
)

# Browser → backend direct calls with credentials: 'include'.
# allow_credentials=True is required for cookies (httpOnly auth cookies) to be sent and received.
# Wildcard origins ("*") are incompatible with allow_credentials, so the origin is explicit.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chat_threads_router)
app.include_router(chat_messages_router)
app.include_router(documents_router)


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
        content={"detail": "An unexpected server error occurred"},
    )


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Liveness probe — returns 200 if the service is running."""
    return {"status": "ok"}
