"""LLM factory — returns the configured LLM provider instance.

Reads LLM_PROVIDER from settings (default: "gemini"). Supported values:
  gemini      — ChatGoogleGenerativeAI (existing provider)
  cloudflare  — CloudflareLLM (Cloudflare Workers AI REST API)

Purpose variants:
  general  → main chat model
  sql      → code/SQL generation model (may differ per provider)
  router   → lightweight classification model
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.7, purpose: str = "general"):
    """Return an LLM instance for the configured provider."""
    if settings.LLM_PROVIDER == "cloudflare":
        from app.core.exceptions import LLMProviderError
        from app.services.cloudflare_llm import CloudflareLLM

        if not settings.CLOUDFLARE_ACCOUNT_ID or not settings.CLOUDFLARE_API_TOKEN:
            raise LLMProviderError(
                "Cloudflare",
                "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must be set",
            )
        model_map = {
            "sql": settings.CLOUDFLARE_SQL_MODEL,
            "router": settings.CLOUDFLARE_ROUTER_MODEL,
            "general": settings.CLOUDFLARE_MODEL,
        }
        model = model_map.get(purpose, settings.CLOUDFLARE_MODEL)
        logger.info("Using Cloudflare Workers AI — model: %s", model)
        return CloudflareLLM(model=model, temperature=temperature)
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI

        logger.info("Using Gemini — model: %s", settings.GEMINI_LLM_MODEL)
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_LLM_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
        )


def get_router_llm():
    return get_llm(temperature=0.0, purpose="router")


def get_synthesis_llm():
    return get_llm(temperature=0.7, purpose="general")


def get_sql_llm():
    return get_llm(temperature=0.1, purpose="sql")
