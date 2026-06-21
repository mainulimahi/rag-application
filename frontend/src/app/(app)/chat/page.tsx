'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { chatApi, authApi } from '@/lib/api/client'
import type { ChatThread } from '@/lib/types'
import type { DisplayMessage } from '@/components/chat/ChatMessages'
import ChatSidebar from '@/components/chat/ChatSidebar'
import ChatMessages from '@/components/chat/ChatMessages'
import ChatInput from '@/components/chat/ChatInput'

// Stable IDs for the two optimistic placeholder messages shown while the LLM
// is running. Using constants avoids a dependency on crypto.randomUUID().
const PENDING_USER_ID = '__pending_user__'
const PENDING_ASSISTANT_ID = '__pending_assistant__'

export default function ChatPage() {
  const router = useRouter()

  const [threads, setThreads] = useState<ChatThread[]>([])
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)

  const initDone = useRef(false)

  // ── Thread helpers ──────────────────────────────────────────────────────────

  const loadThreads = useCallback(async (): Promise<ChatThread[]> => {
    const data = await chatApi.listThreads()
    setThreads(data)
    return data
  }, [])

  const selectThread = useCallback(async (threadId: string) => {
    setSelectedThreadId(threadId)
    setIsLoadingMessages(true)
    try {
      const data = await chatApi.listMessages(threadId)
      setMessages(data)
    } catch {
      setMessages([])
    } finally {
      setIsLoadingMessages(false)
    }
  }, [])

  // ── Initial load ────────────────────────────────────────────────────────────

  useEffect(() => {
    if (initDone.current) return
    initDone.current = true

    async function init() {
      try {
        const existing = await loadThreads()
        if (existing.length > 0) {
          await selectThread(existing[0].id)
        } else {
          const thread = await chatApi.createThread()
          setThreads([thread])
          setSelectedThreadId(thread.id)
          setMessages([])
        }
      } catch {
        // Auth failure — middleware will redirect.
      }
    }

    init()
  }, [loadThreads, selectThread])

  // ── Thread handlers ─────────────────────────────────────────────────────────

  async function handleNewChat() {
    try {
      const thread = await chatApi.createThread()
      setThreads((prev) => [thread, ...prev])
      setSelectedThreadId(thread.id)
      setMessages([])
    } catch (err) {
      console.error('Failed to create thread', err)
    }
  }

  async function handleSelectThread(id: string) {
    if (id === selectedThreadId) return
    await selectThread(id)
  }

  async function handleRenameThread(id: string, title: string) {
    try {
      const updated = await chatApi.renameThread(id, title)
      setThreads((prev) => prev.map((t) => (t.id === id ? updated : t)))
    } catch (err) {
      console.error('Failed to rename thread', err)
    }
  }

  async function handleDeleteThread(id: string) {
    try {
      await chatApi.deleteThread(id)
      const remaining = threads.filter((t) => t.id !== id)
      setThreads(remaining)
      if (selectedThreadId === id) {
        if (remaining.length > 0) {
          await selectThread(remaining[0].id)
        } else {
          const thread = await chatApi.createThread()
          setThreads([thread])
          setSelectedThreadId(thread.id)
          setMessages([])
        }
      }
    } catch (err) {
      console.error('Failed to delete thread', err)
    }
  }

  // ── Message handlers ────────────────────────────────────────────────────────

  async function handleSendMessage(content: string) {
    if (!selectedThreadId || isGenerating) return

    // Optimistically add the user message and a typing placeholder so the UI
    // doesn't appear frozen while waiting for the LLM (which can take seconds).
    const pendingUser: DisplayMessage = {
      id: PENDING_USER_ID,
      thread_id: selectedThreadId,
      user_id: '',
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      edited_at: null,
      isPending: true,
    }
    const pendingAssistant: DisplayMessage = {
      id: PENDING_ASSISTANT_ID,
      thread_id: selectedThreadId,
      user_id: '',
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      edited_at: null,
      isPending: true,
    }
    setMessages((prev) => [...prev, pendingUser, pendingAssistant])
    setIsGenerating(true)

    try {
      const result = await chatApi.createMessage(selectedThreadId, content)

      // Replace both pending placeholders with the real server messages.
      setMessages((prev) => [
        ...prev.filter((m) => !m.isPending),
        result.user_message,
        result.assistant_message,
      ])

      // Update the thread in the sidebar (title may have been auto-generated,
      // and updated_at has changed so ordering is correct).
      setThreads((prev) =>
        prev.map((t) => (t.id === selectedThreadId ? result.thread : t)),
      )
    } catch (err) {
      // Discard placeholders on error so the UI returns to a clean state.
      setMessages((prev) => prev.filter((m) => !m.isPending))
      console.error('Failed to send message', err)
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleEditMessage(messageId: string, content: string) {
    if (isGenerating) return

    // Show a typing placeholder for the incoming assistant reply while the API
    // is in flight. The pending user message is not shown here because the
    // existing message stays in the list (it's just about to be updated).
    const pendingAssistant: DisplayMessage = {
      id: PENDING_ASSISTANT_ID,
      thread_id: selectedThreadId ?? '',
      user_id: '',
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      edited_at: null,
      isPending: true,
    }
    setMessages((prev) => [...prev, pendingAssistant])
    setIsGenerating(true)

    try {
      const result = await chatApi.updateMessage(messageId, content)

      setMessages((prev) => {
        // 1. Remove the pending placeholder.
        // 2. Remove all messages that the server deleted (subsequent messages).
        // 3. Update the edited user message.
        // 4. Append the new assistant reply.
        const deletedSet = new Set(result.deleted_message_ids)
        return [
          ...prev
            .filter((m) => !m.isPending && !deletedSet.has(m.id))
            .map((m) => (m.id === messageId ? result.updated_message : m)),
          result.assistant_message,
        ]
      })
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.isPending))
      console.error('Failed to edit message', err)
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleRegenerateMessage(messageId: string) {
    if (isGenerating) return

    setRegeneratingId(messageId)
    setIsGenerating(true)

    try {
      const result = await chatApi.regenerateMessage(messageId)
      // The message ID stays the same — just swap the content.
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? result.assistant_message : m)),
      )
    } catch (err) {
      console.error('Failed to regenerate message', err)
    } finally {
      setRegeneratingId(null)
      setIsGenerating(false)
    }
  }

  async function handleLogout() {
    await authApi.logout()
    router.push('/login')
    router.refresh()
  }

  // ── Derived ─────────────────────────────────────────────────────────────────

  const selectedThread = threads.find((t) => t.id === selectedThreadId)

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="chat-layout">
      <ChatSidebar
        threads={threads}
        selectedThreadId={selectedThreadId}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        onRenameThread={handleRenameThread}
        onDeleteThread={handleDeleteThread}
        onLogout={handleLogout}
      />

      <div className="chat-main">
        {selectedThread ? (
          <div className="chat-main-header">{selectedThread.title}</div>
        ) : (
          <div className="chat-main-header" style={{ color: 'var(--color-text-muted)' }}>
            Loading…
          </div>
        )}

        {isLoadingMessages ? (
          <div className="chat-messages chat-empty-state">
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9375rem' }}>
              Loading messages…
            </p>
          </div>
        ) : (
          <ChatMessages
            messages={messages}
            isGenerating={isGenerating}
            regeneratingId={regeneratingId}
            onEditMessage={handleEditMessage}
            onRegenerateMessage={handleRegenerateMessage}
          />
        )}

        <ChatInput
          onSend={handleSendMessage}
          disabled={!selectedThreadId || isGenerating}
        />
      </div>
    </div>
  )
}
