"""Generic pagination wrapper — used by all list endpoints that support ?page=&limit=."""

from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    """Standard paginated envelope returned by all paginated list endpoints."""

    items: list[ItemT]
    total: int
    page: int
    limit: int
    pages: int
