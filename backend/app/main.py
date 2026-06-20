"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.users import router as users_router

app = FastAPI(
    title="RAG Application",
    description="Retrieval-Augmented Generation API",
    version="0.1.0",
)

# Allow the Next.js frontend to call the API directly from the browser (e.g. health checks).
# The Next.js BFF routes also call the backend server-to-server, which bypasses CORS entirely.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Liveness probe — returns 200 if the service is running."""
    return {"status": "ok"}
