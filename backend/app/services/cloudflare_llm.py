"""Cloudflare Workers AI LLM client.

Uses the Cloudflare REST API (OpenAI-compatible response format).
Supports both the new OpenAI-compatible format (choices[0].message.content)
and the older simple format (result.response).
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.config import settings
from app.core.exceptions import LLMProviderError, RateLimitError

logger = logging.getLogger(__name__)

_CF_BASE = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
)


def _to_cf_messages(messages: list[BaseMessage]) -> list[dict]:
    result: list[dict] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": str(msg.content)})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": str(msg.content)})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": str(msg.content)})
    return result


class CloudflareLLM:
    """Minimal async LangChain-compatible wrapper for Cloudflare Workers AI."""

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._url = _CF_BASE.format(
            account_id=settings.CLOUDFLARE_ACCOUNT_ID,
            model=model,
        )
        self._headers = {
            "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json",
        }

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        cf_messages = _to_cf_messages(messages)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self._url,
                    headers=self._headers,
                    json={
                        "messages": cf_messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    },
                )

                if response.status_code == 429:
                    retry_after: int | None = None
                    try:
                        data = response.json()
                        if data.get("errors"):
                            retry_after = 60
                    except Exception:
                        pass
                    logger.warning(
                        "Cloudflare rate limit hit on model %s", self.model
                    )
                    raise RateLimitError("Cloudflare Workers AI", retry_after)

                if response.status_code != 200:
                    logger.error(
                        "Cloudflare API error %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    raise LLMProviderError(
                        "Cloudflare Workers AI", f"HTTP {response.status_code}"
                    )

                data = response.json()
                if not data.get("success"):
                    raise LLMProviderError(
                        "Cloudflare Workers AI", str(data.get("errors", []))
                    )

                result = data.get("result", {})
                # OpenAI-compatible format (most models)
                if "choices" in result and result["choices"]:
                    content = result["choices"][0]["message"]["content"]
                # Simple format (some older CF models)
                elif "response" in result:
                    content = result["response"]
                else:
                    raise LLMProviderError(
                        "Cloudflare Workers AI",
                        f"Unexpected response format: {str(result)[:200]}",
                    )

                logger.info(
                    "Cloudflare response: model=%s chars=%d", self.model, len(content)
                )
                return AIMessage(content=content)

        except (RateLimitError, LLMProviderError):
            raise
        except httpx.TimeoutException:
            raise LLMProviderError(
                "Cloudflare Workers AI", "Request timed out after 60 seconds"
            )
        except Exception as exc:
            raise LLMProviderError("Cloudflare Workers AI", str(exc))

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.ainvoke(messages))
        finally:
            loop.close()
