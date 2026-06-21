"""
LLM service — provider interface and Gemini implementation.

Calling code depends only on LLMProvider (a structural Protocol).
To swap providers later, implement the Protocol and update get_llm_provider() —
no changes needed in api/ or services/ callers.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Protocol, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings


class LLMMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class LLMProvider(Protocol):
    """Interface contract for LLM providers. Implement this to swap backends."""

    async def chat(self, messages: list[LLMMessage]) -> str:
        """Generate an assistant reply given a full conversation history."""
        ...

    async def generate_title(self, first_user_message: str) -> str:
        """Generate a concise 3-5 word thread title from the first user message."""
        ...


class GeminiProvider:
    """
    LLM provider backed by Google Gemini via langchain-google-genai.

    Uses two client instances so chat and title generation can have
    different temperatures without recreating the client each call.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._chat_client: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7,
        )
        # Lower temperature for title generation keeps output deterministic.
        self._title_client: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.3,
        )

    async def chat(self, messages: list[LLMMessage]) -> str:
        """
        Send a conversation history to Gemini and return the assistant reply as a string.

        Params:
            messages: Full conversation history in chronological order.
        Returns:
            The assistant's reply text.
        """
        lc_messages: list[BaseMessage] = []
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            else:
                lc_messages.append(AIMessage(content=msg["content"]))
        response = await self._chat_client.ainvoke(lc_messages)
        return str(response.content)

    async def generate_title(self, first_user_message: str) -> str:
        """
        Ask the LLM to produce a short thread title for the first message.

        Returns a 3-5 word title with no surrounding quotes or punctuation.
        Falls back to a truncated version of the message on any error.
        """
        prompt = (
            "Generate a concise 3-5 word title for a chat conversation that begins "
            "with the message below. Return only the title — no quotes, no punctuation, "
            "no explanation.\n\n"
            f"Message: {first_user_message[:500]}"
        )
        try:
            response = await self._title_client.ainvoke([HumanMessage(content=prompt)])
            title = str(response.content).strip().strip('"').strip("'")
            return title if title else first_user_message[:60]
        except Exception:
            return first_user_message[:60]


@lru_cache(maxsize=1)
def get_llm_provider() -> GeminiProvider:
    """Return the singleton LLM provider constructed from application settings."""
    return GeminiProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_LLM_MODEL,
    )
