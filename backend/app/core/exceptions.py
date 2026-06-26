"""Custom exceptions for LLM provider errors."""

from __future__ import annotations


class RateLimitError(Exception):
    def __init__(self, provider: str, retry_after: int | None = None) -> None:
        self.provider = provider
        self.retry_after = retry_after
        msg = f"{provider} rate limit reached."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)


class LLMProviderError(Exception):
    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"{provider} error: {message}")
