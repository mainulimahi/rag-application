"""Chat thread and message endpoints.

Two routers:
- threads_router: /api/chat-threads  — thread CRUD + message list/create
- messages_router: /api/chat-messages — edit, regenerate a single message

All LLM calls go through the LangGraph RAG agent (app/agents/), which routes
each query to document retrieval, web search, both, or plain LLM automatically.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import run_agent
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    EditMessageResponse,
    MessageCreate,
    MessagePairResponse,
    MessageResponse,
    MessageUpdate,
    RegenerateResponse,
    ThreadCreate,
    ThreadResponse,
    ThreadUpdate,
)
from app.schemas.pagination import PaginatedResponse
from app.services import chat_service
from app.services.llm_service import LLMMessage, get_llm_provider

threads_router = APIRouter(prefix="/api/chat-threads", tags=["chat-threads"])
messages_router = APIRouter(prefix="/api/chat-messages", tags=["chat-messages"])


# ── Thread CRUD ───────────────────────────────────────────────────────────────


@threads_router.get(
    "",
    response_model=PaginatedResponse[ThreadResponse],
    summary="List chat threads",
)
async def list_chat_threads(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Threads per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[ThreadResponse]:
    """Return a page of chat threads for the authenticated user, most recently updated first."""
    threads, total = await chat_service.list_threads_paginated(db, current_user.id, page, limit)
    pages = max(1, (total + limit - 1) // limit)
    return PaginatedResponse(
        items=[ThreadResponse.model_validate(t) for t in threads],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@threads_router.post(
    "",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chat thread",
)
async def create_chat_thread(
    body: ThreadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThreadResponse:
    """Create a new chat thread for the authenticated user."""
    return await chat_service.create_thread(db, current_user.id, body.title)


@threads_router.patch(
    "/{thread_id}",
    response_model=ThreadResponse,
    summary="Rename a chat thread",
)
async def rename_chat_thread(
    thread_id: UUID,
    body: ThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThreadResponse:
    """Rename a chat thread. Returns 404 if not found or not owned by the user."""
    thread = await chat_service.rename_thread(db, thread_id, current_user.id, body.title)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


@threads_router.delete(
    "/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat thread",
)
async def delete_chat_thread(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a thread and all its messages (cascade). Returns 404 if not found or not owned."""
    deleted = await chat_service.delete_thread(db, thread_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")


# ── Messages ──────────────────────────────────────────────────────────────────


@threads_router.get(
    "/{thread_id}/messages",
    response_model=PaginatedResponse[MessageResponse],
    summary="List messages in a thread",
)
async def list_thread_messages(
    thread_id: UUID,
    page: int = Query(1, ge=1, description="Page number — page 1 contains the most recent messages"),
    limit: int = Query(50, ge=1, le=200, description="Messages per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[MessageResponse]:
    """
    Return a page of messages in a thread in chronological order.

    Page 1 contains the most recent messages (newest-first fetch, then reversed for display).
    To load older messages, increment the page number.
    404 if the thread doesn't exist or isn't owned by the user.
    """
    messages, total = await chat_service.list_messages_paginated(
        db, thread_id, current_user.id, page, limit
    )
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    pages = max(1, (total + limit - 1) // limit)
    return PaginatedResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@threads_router.post(
    "/{thread_id}/messages",
    response_model=MessagePairResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message and receive the assistant reply",
)
async def create_thread_message(
    thread_id: UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessagePairResponse:
    """
    Append a user message, run the RAG agent with the full thread history, and
    store the assistant reply with its sources label. If this is the first message
    the thread title is auto-generated via a short LLM call.
    Returns both messages and the (possibly updated) thread.
    """
    # Count before insert so we can detect the first message pair.
    msg_count_before = await chat_service.count_thread_messages(db, thread_id, current_user.id)

    user_msg = await chat_service.create_message(db, thread_id, current_user.id, body.content)
    if user_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # Build conversation history for the agent (includes the just-stored user message).
    history = await chat_service.list_messages(db, thread_id, current_user.id) or []
    llm_messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
        for m in history
    ]

    assistant_content, sources = await run_agent(db, current_user.id, llm_messages)

    assistant_msg = await chat_service.create_assistant_message(
        db, thread_id, current_user.id, assistant_content, sources
    )

    # Auto-title the thread on the very first exchange.
    thread = await chat_service.get_thread(db, thread_id, current_user.id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    if msg_count_before == 0 and thread.title == "New Chat":
        llm = get_llm_provider()
        generated_title = await llm.generate_title(body.content)
        thread = await chat_service.rename_thread(
            db, thread_id, current_user.id, generated_title
        ) or thread

    return MessagePairResponse(
        user_message=MessageResponse.model_validate(user_msg),
        assistant_message=MessageResponse.model_validate(assistant_msg),
        thread=ThreadResponse.model_validate(thread),
    )


# ── Single-message operations ─────────────────────────────────────────────────


@messages_router.patch(
    "/{message_id}",
    response_model=EditMessageResponse,
    summary="Edit a user message and regenerate the assistant reply",
)
async def update_chat_message(
    message_id: UUID,
    body: MessageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EditMessageResponse:
    """
    Update the content of a user message, delete all subsequent messages in the
    thread, run the RAG agent with the updated history, and store a fresh
    assistant reply. Returns the edited message, the new assistant reply, and the
    IDs of every message that was deleted so the frontend can sync its state.
    """
    original = await chat_service.get_message(db, message_id, current_user.id)
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if original.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only user messages can be edited",
        )

    updated_msg = await chat_service.update_message(db, message_id, current_user.id, body.content)
    if updated_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    deleted_ids = await chat_service.delete_messages_after(
        db, message_id, original.thread_id, current_user.id
    )

    # History now ends with the updated user message.
    history = await chat_service.list_messages(db, original.thread_id, current_user.id) or []
    llm_messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
        for m in history
    ]

    assistant_content, sources = await run_agent(db, current_user.id, llm_messages)

    assistant_msg = await chat_service.create_assistant_message(
        db, original.thread_id, current_user.id, assistant_content, sources
    )

    return EditMessageResponse(
        updated_message=MessageResponse.model_validate(updated_msg),
        assistant_message=MessageResponse.model_validate(assistant_msg),
        deleted_message_ids=deleted_ids,
    )


@messages_router.post(
    "/{message_id}/regenerate",
    response_model=RegenerateResponse,
    summary="Regenerate an assistant reply",
)
async def regenerate_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegenerateResponse:
    """
    Re-run the RAG agent for the history preceding an existing assistant message
    and replace that message's content in-place (same ID). Returns the updated
    assistant message. 404 if not found or not owned; 400 if not an assistant message.
    """
    msg = await chat_service.get_message(db, message_id, current_user.id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only assistant messages can be regenerated",
        )

    # History = everything before this assistant message in chronological order.
    history = await chat_service.list_messages_before(
        db, msg.thread_id, current_user.id, msg.created_at
    )
    if not history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No history to regenerate from",
        )

    llm_messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
        for m in history
    ]

    new_content, sources = await run_agent(db, current_user.id, llm_messages)

    updated_msg = await chat_service.replace_assistant_message(
        db, message_id, current_user.id, new_content, sources
    )
    if updated_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    return RegenerateResponse(assistant_message=MessageResponse.model_validate(updated_msg))
