'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { chatApi, authApi, usersApi } from '@/lib/api/client'
import type { ChatThread, User } from '@/lib/types'
import type { DisplayMessage } from '@/components/chat/ChatMessages'
import ChatSidebar from '@/components/chat/ChatSidebar'
import ChatMessages from '@/components/chat/ChatMessages'
import ChatInput from '@/components/chat/ChatInput'

const PENDING_USER_ID = '__pending_user__'
const PENDING_ASSISTANT_ID = '__pending_assistant__'
const THREADS_LIMIT = 20
const MESSAGES_LIMIT = 50

export default function ChatPage() {
  const router = useRouter()

  const [user, setUser] = useState<User | null>(null)
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [threadsPage, setThreadsPage] = useState(1)
  const [threadsHasMore, setThreadsHasMore] = useState(false)
  const [isLoadingMoreThreads, setIsLoadingMoreThreads] = useState(false)
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [messagesPage, setMessagesPage] = useState(1)
  const [messagesHasOlder, setMessagesHasOlder] = useState(false)
  const [isLoadingOlder, setIsLoadingOlder] = useState(false)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)

  const initDone = useRef(false)

  // ── Thread helpers ──────────────────────────────────────────────────────────

  const loadThreads = useCallback(async (): Promise<ChatThread[]> => {
    const data = await chatApi.listThreads(1, THREADS_LIMIT)
    setThreads(data.items)
    setThreadsPage(1)
    setThreadsHasMore(data.pages > 1)
    return data.items
  }, [])

  const selectThread = useCallback(async (threadId: string) => {
    setSelectedThreadId(threadId)
    setChatError(null)
    setIsLoadingMessages(true)
    setMessagesPage(1)
    setMessagesHasOlder(false)
    try {
      const data = await chatApi.listMessages(threadId, 1, MESSAGES_LIMIT)
      setMessages(data.items)
      setMessagesHasOlder(data.pages > 1)
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
        const [currentUser, existing] = await Promise.all([
          usersApi.me(),
          loadThreads(),
        ])
        setUser(currentUser)

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
      setMessagesHasOlder(false)
      setChatError(null)
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to create chat')
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
      setChatError(err instanceof Error ? err.message : 'Failed to rename chat')
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
          setMessagesHasOlder(false)
        }
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to delete chat')
    }
  }

  async function handleLoadMoreThreads() {
    if (isLoadingMoreThreads) return
    setIsLoadingMoreThreads(true)
    try {
      const nextPage = threadsPage + 1
      const data = await chatApi.listThreads(nextPage, THREADS_LIMIT)
      setThreads((prev) => [...prev, ...data.items])
      setThreadsPage(nextPage)
      setThreadsHasMore(nextPage < data.pages)
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to load more chats')
    } finally {
      setIsLoadingMoreThreads(false)
    }
  }

  async function handleLoadOlderMessages() {
    if (!selectedThreadId || isLoadingOlder) return
    setIsLoadingOlder(true)
    try {
      const nextPage = messagesPage + 1
      const data = await chatApi.listMessages(selectedThreadId, nextPage, MESSAGES_LIMIT)
      // Prepend older messages (they are already in chronological order within the page)
      setMessages((prev) => [...data.items, ...prev])
      setMessagesPage(nextPage)
      setMessagesHasOlder(nextPage < data.pages)
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to load older messages')
    } finally {
      setIsLoadingOlder(false)
    }
  }

  // ── Message handlers ────────────────────────────────────────────────────────

  async function handleSendMessage(content: string) {
    if (!selectedThreadId || isGenerating) return

    setChatError(null)

    const pendingUser: DisplayMessage = {
      id: PENDING_USER_ID,
      thread_id: selectedThreadId,
      user_id: '',
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      edited_at: null,
      sources: null,
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
      sources: null,
      isPending: true,
    }
    setMessages((prev) => [...prev, pendingUser, pendingAssistant])
    setIsGenerating(true)

    try {
      const result = await chatApi.createMessage(selectedThreadId, content)

      setMessages((prev) => [
        ...prev.filter((m) => !m.isPending),
        result.user_message,
        result.assistant_message,
      ])

      setThreads((prev) =>
        prev.map((t) => (t.id === selectedThreadId ? result.thread : t)),
      )
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.isPending))
      setChatError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleEditMessage(messageId: string, content: string) {
    if (isGenerating) return

    setChatError(null)

    const pendingAssistant: DisplayMessage = {
      id: PENDING_ASSISTANT_ID,
      thread_id: selectedThreadId ?? '',
      user_id: '',
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      edited_at: null,
      sources: null,
      isPending: true,
    }
    setMessages((prev) => [...prev, pendingAssistant])
    setIsGenerating(true)

    try {
      const result = await chatApi.updateMessage(messageId, content)

      setMessages((prev) => {
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
      setChatError(err instanceof Error ? err.message : 'Failed to edit message')
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleRegenerateMessage(messageId: string) {
    if (isGenerating) return

    setChatError(null)
    setRegeneratingId(messageId)
    setIsGenerating(true)

    try {
      const result = await chatApi.regenerateMessage(messageId)
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? result.assistant_message : m)),
      )
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Failed to regenerate response')
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
        user={user}
        threadsHasMore={threadsHasMore}
        isLoadingMoreThreads={isLoadingMoreThreads}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        onRenameThread={handleRenameThread}
        onDeleteThread={handleDeleteThread}
        onLoadMoreThreads={handleLoadMoreThreads}
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

        {chatError && (
          <div className="chat-error-banner" role="alert">
            {chatError}
            <button className="chat-error-dismiss" onClick={() => setChatError(null)}>×</button>
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
            messagesHasOlder={messagesHasOlder}
            isLoadingOlder={isLoadingOlder}
            onEditMessage={handleEditMessage}
            onRegenerateMessage={handleRegenerateMessage}
            onLoadOlderMessages={handleLoadOlderMessages}
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
