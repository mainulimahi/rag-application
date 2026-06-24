"""Chat thread and message endpoints.

Two routers:
- threads_router: /api/chat-threads  — thread CRUD + message list/create
- messages_router: /api/chat-messages — edit, regenerate a single message

All LLM calls go through the LangGraph RAG agent (app/agents/), which routes
each query to document retrieval, web search, both, or plain LLM automatically.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import run_agent
from app.agents.graph import stream_agent_events
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    DeleteAllChatsRequest,
    DeleteAllChatsResponse,
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
from app.services.auth_service import verify_password
from app.services.llm_service import LLMMessage, get_llm_provider
from app.services.user_service import get_user_by_id

threads_router = APIRouter(prefix="/api/chat-threads", tags=["chat-threads"])
messages_router = APIRouter(prefix="/api/chat-messages", tags=["chat-messages"])

logger = logging.getLogger(__name__)


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


@threads_router.patch(
    "/{thread_id}/pin",
    response_model=ThreadResponse,
    summary="Toggle the pinned state of a chat thread",
)
async def pin_chat_thread(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ThreadResponse:
    """
    Toggle pinned on a thread. Pinned threads appear at the top of the sidebar
    and cannot be deleted until unpinned.
    Returns 404 if not found or not owned by the user.
    """
    thread = await chat_service.toggle_pin_thread(db, thread_id, current_user.id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return ThreadResponse.model_validate(thread)


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
    """
    Delete a thread and all its messages (cascade). Returns 404 if not found or not owned.
    Returns 400 if the thread is pinned — unpin it first.
    """
    result = await chat_service.delete_thread(db, thread_id, current_user.id)
    if result is False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    if result == "pinned":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unpin this thread before deleting",
        )


@threads_router.delete(
    "",
    response_model=DeleteAllChatsResponse,
    summary="Delete all non-pinned chat threads",
)
async def delete_all_chat_threads(
    body: DeleteAllChatsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteAllChatsResponse:
    """
    Soft-delete all non-pinned threads for the authenticated user (hard-deletes their messages).
    Requires password confirmation to prevent accidental data loss.
    Returns 401 if the password is incorrect.
    """
    user = await get_user_by_id(db, current_user.id)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    deleted_count = await chat_service.delete_all_non_pinned_threads(db, current_user.id)
    return DeleteAllChatsResponse(deleted_count=deleted_count)


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
    msg_count_before = await chat_service.count_thread_messages(db, thread_id, current_user.id)

    user_msg = await chat_service.create_message(db, thread_id, current_user.id, body.content)
    if user_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    history = await chat_service.list_messages(db, thread_id, current_user.id) or []
    llm_messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
        for m in history
    ]

    assistant_content, sources, input_tokens, output_tokens, data_analysis_result = (
        await run_agent(db, current_user.id, llm_messages)
    )

    assistant_msg = await chat_service.create_assistant_message(
        db, thread_id, current_user.id, assistant_content, sources, input_tokens, output_tokens
    )

    thread = await chat_service.get_thread(db, thread_id, current_user.id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    if msg_count_before == 0 and thread.title == "New Chat":
        llm = get_llm_provider()
        generated_title = await llm.generate_title(body.content)
        thread = await chat_service.rename_thread(
            db, thread_id, current_user.id, generated_title
        ) or thread

    assistant_response = MessageResponse.model_validate(assistant_msg)
    assistant_response.data_analysis = data_analysis_result

    return MessagePairResponse(
        user_message=MessageResponse.model_validate(user_msg),
        assistant_message=assistant_response,
        thread=ThreadResponse.model_validate(thread),
    )


@threads_router.post(
    "/{thread_id}/messages/stream",
    summary="Send a message and receive an SSE streaming response",
)
async def create_thread_message_stream(
    thread_id: UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE streaming variant of POST /{thread_id}/messages.

    Emits a sequence of Server-Sent Events:
      {"type": "status",  "content": "🔍 Searching..."}   — node progress
      {"type": "token",   "content": "..."}                — individual tokens
      {"type": "done",    "user_message": {...},
                          "assistant_message": {...},
                          "thread": {...}}                  — final stored data
      {"type": "error",   "content": "..."}                — on failure

    The frontend falls back to the non-streaming endpoint if this one errors.
    X-Accel-Buffering: no disables nginx response buffering for the stream.
    """
    msg_count_before = await chat_service.count_thread_messages(db, thread_id, current_user.id)

    user_msg = await chat_service.create_message(db, thread_id, current_user.id, body.content)
    if user_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    history = await chat_service.list_messages(db, thread_id, current_user.id) or []
    llm_messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
        for m in history
    ]

    user_msg_data = MessageResponse.model_validate(user_msg).model_dump(mode="json")

    async def generate():
        try:
            final_answer = ""
            final_sources = "llm_only"
            final_input_tokens = 0
            final_output_tokens = 0
            final_data_analysis: dict | None = None

            async for event in stream_agent_events(db, current_user.id, llm_messages):
                if event["type"] == "final":
                    final_answer = event["answer"]
                    final_sources = event["sources"]
                    final_input_tokens = event.get("input_tokens", 0)
                    final_output_tokens = event.get("output_tokens", 0)
                    final_data_analysis = event.get("data_analysis_result")
                else:
                    yield f"data: {json.dumps(event)}\n\n"

            assistant_msg = await chat_service.create_assistant_message(
                db, thread_id, current_user.id, final_answer, final_sources,
                final_input_tokens, final_output_tokens,
            )

            thread = await chat_service.get_thread(db, thread_id, current_user.id)
            if msg_count_before == 0 and thread and thread.title == "New Chat":
                llm_provider = get_llm_provider()
                generated_title = await llm_provider.generate_title(body.content)
                thread = await chat_service.rename_thread(
                    db, thread_id, current_user.id, generated_title
                ) or thread

            assistant_msg_response = MessageResponse.model_validate(assistant_msg)
            assistant_msg_response.data_analysis = final_data_analysis

            done_payload = {
                "type": "done",
                "user_message": user_msg_data,
                "assistant_message": assistant_msg_response.model_dump(mode="json"),
                "thread": ThreadResponse.model_validate(thread).model_dump(mode="json")
                if thread
                else None,
                "data_analysis": final_data_analysis,
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as exc:
            logger.error("SSE stream error for thread %s: %s", thread_id, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Stream failed — please retry'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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

    history = await chat_service.list_messages(db, original.thread_id, current_user.id) or []
    llm_messages: list[LLMMessage] = [
        {"role": m.role, "content": m.content}  # type: ignore[typeddict-item]
        for m in history
    ]

    assistant_content, sources, input_tokens, output_tokens, data_analysis_result = (
        await run_agent(db, current_user.id, llm_messages)
    )

    assistant_msg = await chat_service.create_assistant_message(
        db, original.thread_id, current_user.id, assistant_content, sources,
        input_tokens, output_tokens,
    )

    assistant_response = MessageResponse.model_validate(assistant_msg)
    assistant_response.data_analysis = data_analysis_result

    return EditMessageResponse(
        updated_message=MessageResponse.model_validate(updated_msg),
        assistant_message=assistant_response,
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

    new_content, sources, input_tokens, output_tokens, data_analysis_result = (
        await run_agent(db, current_user.id, llm_messages)
    )

    updated_msg = await chat_service.replace_assistant_message(
        db, message_id, current_user.id, new_content, sources, input_tokens, output_tokens
    )
    if updated_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    assistant_response = MessageResponse.model_validate(updated_msg)
    assistant_response.data_analysis = data_analysis_result

    return RegenerateResponse(assistant_message=assistant_response)
