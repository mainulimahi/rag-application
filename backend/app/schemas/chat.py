"""Pydantic request/response schemas for chat threads and messages."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ThreadCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=500)


class ThreadUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class ThreadResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    user_id: UUID
    role: str
    content: str
    created_at: datetime
    edited_at: datetime | None

    model_config = {"from_attributes": True}


class MessagePairResponse(BaseModel):
    """Returned by POST /api/chat-threads/{thread_id}/messages after LLM generation.

    Includes the stored user message, the assistant reply, and the updated thread
    (so the frontend can refresh the auto-generated title in the sidebar).
    """

    user_message: MessageResponse
    assistant_message: MessageResponse
    thread: ThreadResponse


class EditMessageResponse(BaseModel):
    """Returned by PATCH /api/chat-messages/{message_id} after edit + LLM regeneration.

    deleted_message_ids lists every message that was purged because it came after
    the edited message — the frontend removes them from local state.
    """

    updated_message: MessageResponse
    assistant_message: MessageResponse
    deleted_message_ids: list[UUID]


class RegenerateResponse(BaseModel):
    """Returned by POST /api/chat-messages/{message_id}/regenerate."""

    assistant_message: MessageResponse
