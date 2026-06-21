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
    """Return all threads owned by user_id, ordered by most recently updated first."""
    result = await db.execute(
        sa.select(ChatThread)
        .where(ChatThread.user_id == user_id)
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
    """Return a thread only if it exists and belongs to user_id."""
    result = await db.execute(
        sa.select(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.user_id == user_id,
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
) -> bool:
    """
    Delete a thread and cascade-delete its messages.

    Returns False if the thread doesn't exist or isn't owned by user_id.
    The DB cascade (ON DELETE CASCADE) handles message cleanup.
    """
    thread = await get_thread(db, thread_id, user_id)
    if thread is None:
        return False
    await db.delete(thread)
    await db.commit()
    return True


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
    db: AsyncSession, thread_id: UUID, user_id: UUID, content: str
) -> ChatMessage:
    """
    Append an assistant message to a thread.

    Also bumps thread.updated_at so it stays at the top of the sidebar list.
    """
    message = ChatMessage(
        thread_id=thread_id,
        user_id=user_id,
        role="assistant",
        content=content,
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
    db: AsyncSession, message_id: UUID, user_id: UUID, new_content: str
) -> ChatMessage | None:
    """
    Replace the content of an existing assistant message in-place.

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
    await db.commit()
    await db.refresh(message)
    return message
