"""
Embedding service — provider interface and Gemini implementation.

Calling code depends only on EmbeddingProvider (a structural Protocol).
To swap providers later, implement the Protocol and update get_embedding_provider() —
no changes needed in api/ or services/ callers.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings


class EmbeddingProvider(Protocol):
    """Interface contract for embedding providers. Implement this to swap backends."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts. Returns one vector per input text."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Generate an embedding for a single query string."""
        ...


class GeminiEmbeddingProvider:
    """
    Embedding provider backed by Google Gemini via langchain-google-genai.

    Uses gemini-embedding-001 which produces 768-dimensional vectors.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=api_key,
        )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Params:
            texts: List of text strings to embed.
        Returns:
            List of 768-dimensional float vectors, one per input text.
        """
        return await self._client.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        """
        Generate an embedding for a single query string.

        Params:
            text: The query string to embed.
        Returns:
            A 768-dimensional float vector.
        """
        return await self._client.aembed_query(text)


@lru_cache(maxsize=1)
def get_embedding_provider() -> GeminiEmbeddingProvider:
    """Return the singleton embedding provider constructed from application settings."""
    return GeminiEmbeddingProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_EMBEDDING_MODEL,
    )
