'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { chatApi, authApi, usersApi } from '@/lib/api/client'
import type { ChatThread, User } from '@/lib/types'
import type { DisplayMessage } from '@/components/chat/ChatMessages'
import ChatSidebar from '@/components/chat/ChatSidebar'
import ChatMessages from '@/components/chat/ChatMessages'
import ChatInput from '@/components/chat/ChatInput'
import RateLimitBanner from '@/components/chat/RateLimitBanner'
import { showToast, ToastContainer } from '@/components/Toast'

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

  // selectedThreadId === null means a pending (unsaved) new chat is active
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  // hasPendingChat === true when the user is on an unsaved new chat (no thread created yet)
  const [hasPendingChat, setHasPendingChat] = useState(false)

  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [messagesPage, setMessagesPage] = useState(1)
  const [messagesHasOlder, setMessagesHasOlder] = useState(false)
  const [isLoadingOlder, setIsLoadingOlder] = useState(false)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [streamingStatus, setStreamingStatus] = useState('')
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [providerError, setProviderError] = useState<{
    error_type: 'rate_limit' | 'provider_error'
    provider?: string
    message: string
  } | null>(null)

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
    setHasPendingChat(false)
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
          // No threads yet — show pending new chat without creating a DB row
          setHasPendingChat(true)
          setMessages([])
        }
      } catch {
        // Auth failure — middleware redirects to /login
      }
    }

    init()
  }, [loadThreads, selectThread])

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        handleNewChat()
      }
      if (e.key === 'Escape' && mobileOpen) {
        setMobileOpen(false)
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mobileOpen])

  // ── Thread handlers ─────────────────────────────────────────────────────────

  function handleNewChat() {
    // If already showing a pending (unsaved) chat, do nothing — don't stack empties
    if (hasPendingChat && !selectedThreadId) return
    setSelectedThreadId(null)
    setHasPendingChat(true)
    setMessages([])
    setMessagesHasOlder(false)
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
      showToast(err instanceof Error ? err.message : 'Failed to rename chat', 'error')
    }
  }

  async function handlePinThread(id: string) {
    try {
      const updated = await chatApi.pinThread(id)
      setThreads((prev) => prev.map((t) => (t.id === id ? updated : t)))
      showToast(updated.pinned ? 'Thread pinned' : 'Thread unpinned', 'info')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to pin thread', 'error')
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
          setSelectedThreadId(null)
          setHasPendingChat(true)
          setMessages([])
          setMessagesHasOlder(false)
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete chat'
      if (msg.toLowerCase().includes('unpin')) {
        showToast('Unpin this thread before deleting it', 'error')
      } else {
        showToast(msg, 'error')
      }
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
      showToast(err instanceof Error ? err.message : 'Failed to load more chats', 'error')
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
      setMessages((prev) => [...data.items, ...prev])
      setMessagesPage(nextPage)
      setMessagesHasOlder(nextPage < data.pages)
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to load older messages', 'error')
    } finally {
      setIsLoadingOlder(false)
    }
  }

  // ── Message sending: create thread lazily on first message ──────────────────

  async function handleSendMessage(content: string) {
    if (isGenerating) return
    setProviderError(null)

    // If no thread exists yet, create one now (first message in pending chat)
    let threadId = selectedThreadId
    if (!threadId) {
      if (!hasPendingChat) return
      try {
        const newThread = await chatApi.createThread()
        setThreads((prev) => [newThread, ...prev])
        setSelectedThreadId(newThread.id)
        setHasPendingChat(false)
        threadId = newThread.id
      } catch (err) {
        showToast(err instanceof Error ? err.message : 'Failed to create chat', 'error')
        return
      }
    }

    const pendingUser: DisplayMessage = {
      id: PENDING_USER_ID,
      thread_id: threadId,
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
      thread_id: threadId,
      user_id: '',
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      edited_at: null,
      sources: null,
      isPending: true,
      isStreaming: false,
    }
    setMessages((prev) => [...prev, pendingUser, pendingAssistant])
    setIsGenerating(true)
    setStreamingStatus('')

    try {
      const stream = chatApi.streamMessage(threadId, content)
      let streamingContent = ''

      for await (const event of stream) {
        if (event.type === 'status') {
          setStreamingStatus(event.content)
        } else if (event.type === 'token') {
          streamingContent += event.content
          const snapshot = streamingContent
          setMessages((prev) =>
            prev.map((m) =>
              m.id === PENDING_ASSISTANT_ID
                ? { ...m, content: snapshot, isStreaming: true }
                : m
            )
          )
        } else if (event.type === 'done') {
          setMessages((prev) => [
            ...prev.filter((m) => !m.isPending),
            event.user_message,
            event.assistant_message,
          ])
          if (event.thread) {
            setThreads((prev) =>
              prev.map((t) => (t.id === threadId ? event.thread! : t))
            )
          }
        } else if (event.type === 'error') {
          if (event.error_type === 'rate_limit' || event.error_type === 'provider_error') {
            setProviderError({
              error_type: event.error_type,
              provider: event.provider,
              message: event.content,
            })
            setMessages((prev) => prev.filter((m) => !m.isPending))
            break
          }
          throw new Error(event.content)
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('Stream request failed')) {
        await sendNonStreaming(threadId, content)
        return
      }
      setMessages((prev) => prev.filter((m) => !m.isPending))
      showToast(msg || 'Failed to send message', 'error')
    } finally {
      setIsGenerating(false)
      setStreamingStatus('')
    }
  }

  async function sendNonStreaming(threadId: string, content: string) {
    try {
      const result = await chatApi.createMessage(threadId, content)
      setMessages((prev) => [
        ...prev.filter((m) => !m.isPending),
        result.user_message,
        result.assistant_message,
      ])
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? result.thread : t))
      )
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !m.isPending))
      showToast(err instanceof Error ? err.message : 'Failed to send message', 'error')
    } finally {
      setIsGenerating(false)
      setStreamingStatus('')
    }
  }

  // ── Edit & regenerate ───────────────────────────────────────────────────────

  async function handleEditMessage(messageId: string, content: string) {
    if (isGenerating) return

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
      showToast(err instanceof Error ? err.message : 'Failed to edit message', 'error')
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
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? result.assistant_message : m))
      )
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to regenerate response', 'error')
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
        hasPendingChat={hasPendingChat}
        user={user}
        threadsHasMore={threadsHasMore}
        isLoadingMoreThreads={isLoadingMoreThreads}
        mobileOpen={mobileOpen}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        onRenameThread={handleRenameThread}
        onDeleteThread={handleDeleteThread}
        onPinThread={handlePinThread}
        onLoadMoreThreads={handleLoadMoreThreads}
        onLogout={handleLogout}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="chat-main">
        <div className="chat-main-header">
          <button className="mobile-menu-btn" onClick={() => setMobileOpen(true)} title="Open sidebar">
            <HamburgerIcon />
          </button>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {hasPendingChat && !selectedThreadId ? 'New Chat' : selectedThread?.title ?? 'Loading…'}
          </span>
        </div>

        {providerError && (
          <RateLimitBanner
            error_type={providerError.error_type}
            provider={providerError.provider}
            message={providerError.message}
            onDismiss={() => setProviderError(null)}
          />
        )}

        <ChatMessages
          messages={messages}
          isGenerating={isGenerating}
          streamingStatus={streamingStatus}
          regeneratingId={regeneratingId}
          messagesHasOlder={messagesHasOlder}
          isLoadingOlder={isLoadingOlder}
          isLoadingMessages={isLoadingMessages}
          onEditMessage={handleEditMessage}
          onRegenerateMessage={handleRegenerateMessage}
          onLoadOlderMessages={handleLoadOlderMessages}
          onSuggestedPrompt={(text) => handleSendMessage(text)}
        />

        <ChatInput
          onSend={handleSendMessage}
          disabled={isGenerating}
        />
      </div>

      <ToastContainer />
    </div>
  )
}

function HamburgerIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}
