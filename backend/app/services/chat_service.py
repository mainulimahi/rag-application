"""
Chat service — CRUD for chat threads and messages.

All operations are scoped to a user_id; no cross-user data access is possible.
Every method that touches user-owned data takes user_id as a required parameter
and filters all DB queries by it — this is the multi-tenancy security boundary.
"""

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatThread


async def list_threads(db: AsyncSession, user_id: UUID) -> list[ChatThread]:
    """Return all non-deleted threads owned by user_id, ordered by most recently updated first."""
    result = await db.execute(
        sa.select(ChatThread)
        .where(ChatThread.user_id == user_id, ChatThread.deleted_at.is_(None))
        .order_by(ChatThread.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_thread(
    db: AsyncSession, user_id: UUID, title: str = "New Chat"
) -> ChatThread:
    """Create a new chat thread for the user."""
    thread = ChatThread(user_id=user_id, title=title)
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


async def get_thread(
    db: AsyncSession, thread_id: UUID, user_id: UUID
) -> ChatThread | None:
    """Return a thread only if it exists, belongs to user_id, and is not soft-deleted."""
    result = await db.execute(
        sa.select(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.user_id == user_id,
            ChatThread.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def rename_thread(
    db: AsyncSession, thread_id: UUID, user_id: UUID, title: str
) -> ChatThread | None:
    """
    Rename a thread.

    Returns None if the thread doesn't exist or isn't owned by user_id.
    """
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return None
    thread.title = title
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(thread)
    return thread


async def delete_thread(
    db: AsyncSession, thread_id: UUID, user_id: UUID
) -> bool | str:
    """
    Soft-delete a thread by setting deleted_at to the current time.

    Returns False if not found, the string "pinned" if the thread is pinned,
    or True on success.
    """
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return False
    if thread.pinned:
        return "pinned"
    thread.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def toggle_pin_thread(
    db: AsyncSession, thread_id: UUID, user_id: UUID
) -> "ChatThread | None":
    """Toggle the pinned state of a thread. Returns None if not found or not owned."""
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return None
    thread.pinned = not thread.pinned
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(thread)
    return thread


async def list_messages(
    db: AsyncSession, thread_id: UUID, user_id: UUID
) -> list[ChatMessage] | None:
    """
    Return all messages in a thread in chronological order.

    Returns None if the thread doesn't exist or isn't owned by user_id,
    so the caller can distinguish "not found / no access" from "empty thread".
    """
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return None
    result = await db.execute(
        sa.select(ChatMessage)
        .where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.user_id == user_id,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def create_message(
    db: AsyncSession, thread_id: UUID, user_id: UUID, content: str
) -> ChatMessage | None:
    """
    Append a user message to a thread.

    Also bumps thread.updated_at so it rises to the top of the sidebar list.
    Returns None if the thread doesn't exist or isn't owned by user_id.
    """
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return None

    message = ChatMessage(
        thread_id=thread_id,
        user_id=user_id,
        role="user",
        content=content,
    )
    db.add(message)
    thread.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(message)
    return message


async def get_message(
    db: AsyncSession, message_id: UUID, user_id: UUID
) -> ChatMessage | None:
    """Return a message only if it exists and belongs to user_id."""
    result = await db.execute(
        sa.select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_message(
    db: AsyncSession, message_id: UUID, user_id: UUID, content: str
) -> ChatMessage | None:
    """
    Update the content of a user message and record the edit timestamp.

    Returns None if the message doesn't exist or isn't owned by user_id.
    """
    message = await get_message(db, message_id, user_id)
    if message is None:
        return None
    message.content = content
    message.edited_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)
    return message


async def count_thread_messages(
    db: AsyncSession, thread_id: UUID, user_id: UUID
) -> int:
    """Return the number of messages in a thread, or 0 if thread not found/not owned."""
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return 0
    result = await db.execute(
        sa.select(sa.func.count()).where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.user_id == user_id,
        )
    )
    return result.scalar_one()


async def create_assistant_message(
    db: AsyncSession,
    thread_id: UUID,
    user_id: UUID,
    content: str,
    sources: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> ChatMessage:
    """
    Append an assistant message to a thread.

    sources indicates which tools the RAG agent used: 'llm_only', 'retrieval',
    'web_search', or 'both'. Stored for display in the frontend source badge.
    Also bumps thread.updated_at so it stays at the top of the sidebar list.
    """
    message = ChatMessage(
        thread_id=thread_id,
        user_id=user_id,
        role="assistant",
        content=content,
        sources=sources,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(message)
    thread = await get_thread(db, thread_id, user_id)
    if thread is not None:
        thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)
    return message


async def delete_messages_after(
    db: AsyncSession, message_id: UUID, thread_id: UUID, user_id: UUID
) -> list[UUID]:
    """
    Delete all messages in the thread created after message_id (exclusive).

    Used when a user edits a message — the subsequent exchange is discarded
    so the LLM can regenerate from the edited point forward.
    Returns the list of deleted message IDs so the frontend can update its state.
    """
    ref_result = await db.execute(
        sa.select(ChatMessage.created_at).where(
            ChatMessage.id == message_id,
            ChatMessage.user_id == user_id,
        )
    )
    ref_created_at = ref_result.scalar_one_or_none()
    if ref_created_at is None:
        return []

    # Collect IDs before deleting so we can return them.
    later_result = await db.execute(
        sa.select(ChatMessage.id).where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.user_id == user_id,
            ChatMessage.created_at > ref_created_at,
        )
    )
    deleted_ids: list[UUID] = list(later_result.scalars().all())

    if deleted_ids:
        await db.execute(
            sa.delete(ChatMessage).where(ChatMessage.id.in_(deleted_ids))
        )
        await db.commit()

    return deleted_ids


async def delete_all_non_pinned_threads(db: AsyncSession, user_id: UUID) -> int:
    """
    Hard-delete all messages then soft-delete all non-pinned threads for the user.

    Returns the number of threads soft-deleted.
    """
    # Find non-pinned, non-deleted thread IDs for the user
    thread_result = await db.execute(
        sa.select(ChatThread.id).where(
            ChatThread.user_id == user_id,
            ChatThread.deleted_at.is_(None),
            ChatThread.pinned.is_(False),
        )
    )
    thread_ids = list(thread_result.scalars().all())
    if not thread_ids:
        return 0

    # Hard-delete their messages
    await db.execute(
        sa.delete(ChatMessage).where(
            ChatMessage.thread_id.in_(thread_ids),
            ChatMessage.user_id == user_id,
        )
    )

    # Soft-delete the threads
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.update(ChatThread)
        .where(ChatThread.id.in_(thread_ids))
        .values(deleted_at=now)
    )

    await db.commit()
    return len(thread_ids)


async def list_threads_paginated(
    db: AsyncSession, user_id: UUID, page: int = 1, limit: int = 20
) -> tuple[list[ChatThread], int]:
    """
    Return a page of threads for user_id, ordered by most recently updated first.

    Returns (threads, total_count). Used by the paginated GET /api/chat-threads endpoint.
    Internal callers that need all threads should continue to use list_threads().
    """
    skip = (page - 1) * limit

    count_result = await db.execute(
        sa.select(sa.func.count()).select_from(ChatThread).where(
            ChatThread.user_id == user_id, ChatThread.deleted_at.is_(None)
        )
    )
    total: int = count_result.scalar_one()

    result = await db.execute(
        sa.select(ChatThread)
        .where(ChatThread.user_id == user_id, ChatThread.deleted_at.is_(None))
        .order_by(ChatThread.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def list_messages_paginated(
    db: AsyncSession, thread_id: UUID, user_id: UUID, page: int = 1, limit: int = 50
) -> tuple[list[ChatMessage] | None, int]:
    """
    Return a page of messages from a thread in chronological order.

    Messages are fetched newest-first (DESC) then reversed so the page is
    chronological — this means page 1 contains the most recent messages, which
    is what the frontend needs when first entering a thread.

    Returns (None, 0) if the thread doesn't exist or isn't owned by user_id.
    """
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return None, 0

    skip = (page - 1) * limit

    count_result = await db.execute(
        sa.select(sa.func.count()).select_from(ChatMessage).where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.user_id == user_id,
        )
    )
    total: int = count_result.scalar_one()

    result = await db.execute(
        sa.select(ChatMessage)
        .where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.user_id == user_id,
        )
        .order_by(ChatMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # return in chronological order within the page
    return messages, total


async def list_messages_before(
    db: AsyncSession, thread_id: UUID, user_id: UUID, before_created_at: datetime
) -> list[ChatMessage]:
    """
    Return all messages in the thread created strictly before before_created_at.

    Used by the regenerate flow to reconstruct the history that the LLM should
    respond to (everything before the existing assistant message).
    """
    result = await db.execute(
        sa.select(ChatMessage)
        .where(
            ChatMessage.thread_id == thread_id,
            ChatMessage.user_id == user_id,
            ChatMessage.created_at < before_created_at,
        )
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def replace_assistant_message(
    db: AsyncSession,
    message_id: UUID,
    user_id: UUID,
    new_content: str,
    sources: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> ChatMessage | None:
    """
    Replace the content (and sources) of an existing assistant message in-place.

    Used by the regenerate endpoint — the message keeps its ID so the frontend
    can update its state without re-fetching the whole thread.
    Returns None if the message doesn't exist, isn't owned by user_id,
    or isn't an assistant message.
    """
    result = await db.execute(
        sa.select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.user_id == user_id,
            ChatMessage.role == "assistant",
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None
    message.content = new_content
    message.sources = sources
    message.input_tokens = input_tokens
    message.output_tokens = output_tokens
    await db.commit()
    await db.refresh(message)
    return message
