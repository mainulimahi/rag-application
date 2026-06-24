'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { API_URL } from '@/lib/api/client'
import type { ChatThread, User } from '@/lib/types'

const SIDEBAR_WIDTH_KEY = 'sidebar-width'
const SIDEBAR_COLLAPSED_KEY = 'sidebar-collapsed'
const MIN_WIDTH = 200
const MAX_WIDTH = 400
const DEFAULT_WIDTH = 260

interface Props {
  threads: ChatThread[]
  selectedThreadId: string | null
  hasPendingChat: boolean
  user: User | null
  threadsHasMore: boolean
  isLoadingMoreThreads: boolean
  mobileOpen: boolean
  onSelectThread: (id: string) => void
  onNewChat: () => void
  onRenameThread: (id: string, title: string) => void
  onDeleteThread: (id: string) => void
  onPinThread: (id: string) => void
  onLoadMoreThreads: () => void
  onLogout: () => void
  onCloseMobile: () => void
}

export default function ChatSidebar({
  threads,
  selectedThreadId,
  hasPendingChat,
  user,
  threadsHasMore,
  isLoadingMoreThreads,
  mobileOpen,
  onSelectThread,
  onNewChat,
  onRenameThread,
  onDeleteThread,
  onPinThread,
  onLoadMoreThreads,
  onLogout,
  onCloseMobile,
}: Props) {
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [collapsed, setCollapsed] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WIDTH)
  const renameInputRef = useRef<HTMLInputElement>(null)
  const isDragging = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(DEFAULT_WIDTH)
  const sidebarRef = useRef<HTMLElement>(null)

  // Restore persisted state
  useEffect(() => {
    const savedCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    if (savedCollapsed === 'true') setCollapsed(true)

    const savedWidth = parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY) ?? '', 10)
    if (!isNaN(savedWidth)) setSidebarWidth(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, savedWidth)))
  }, [])

  // Apply inline width when not collapsed
  useEffect(() => {
    if (!sidebarRef.current) return
    if (!collapsed) {
      sidebarRef.current.style.width = `${sidebarWidth}px`
      sidebarRef.current.style.minWidth = `${sidebarWidth}px`
    } else {
      sidebarRef.current.style.width = ''
      sidebarRef.current.style.minWidth = ''
    }
  }, [sidebarWidth, collapsed])

  function toggleCollapse() {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next))
  }

  // ── Resize handle drag ──────────────────────────────────────────────────────

  function handleResizeMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    isDragging.current = true
    startX.current = e.clientX
    startWidth.current = sidebarWidth

    function onMouseMove(ev: MouseEvent) {
      if (!isDragging.current) return
      const delta = ev.clientX - startX.current
      const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth.current + delta))
      setSidebarWidth(newWidth)
    }

    function onMouseUp() {
      isDragging.current = false
      // Persist after drag ends
      setSidebarWidth((w) => {
        localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w))
        return w
      })
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }

  // ── Rename ──────────────────────────────────────────────────────────────────

  function startRename(thread: ChatThread) {
    setRenamingId(thread.id)
    setRenameValue(thread.title)
    setTimeout(() => renameInputRef.current?.select(), 0)
  }

  function commitRename() {
    if (renamingId && renameValue.trim()) {
      onRenameThread(renamingId, renameValue.trim())
    }
    setRenamingId(null)
  }

  function handleRenameKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') commitRename()
    if (e.key === 'Escape') setRenamingId(null)
  }

  function handleDelete(id: string, title: string) {
    if (window.confirm(`Delete "${title}"? This cannot be undone.`)) {
      onDeleteThread(id)
    }
  }

  // ── Derived ─────────────────────────────────────────────────────────────────

  const pinned = threads.filter((t) => t.pinned)
  const unpinned = threads.filter((t) => !t.pinned)

  const initials = user
    ? user.name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
    : '?'

  const avatarSrc = user?.profile_picture_url
    ? `${API_URL}${user.profile_picture_url}`
    : null

  // ── Thread item render ──────────────────────────────────────────────────────

  function ThreadItem({ thread }: { thread: ChatThread }) {
    const isActive = selectedThreadId === thread.id
    const isRenaming = renamingId === thread.id

    return (
      <div
        className={`chat-thread-item${isActive ? ' active' : ''}${thread.pinned ? ' pinned-item' : ''}`}
        onClick={() => {
          if (isRenaming) return
          onSelectThread(thread.id)
          if (mobileOpen) onCloseMobile()
        }}
        title={collapsed ? thread.title : undefined}
      >
        <span className="chat-thread-dot" />
        {isRenaming ? (
          <input
            ref={renameInputRef}
            className="chat-rename-input"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={commitRename}
            onKeyDown={handleRenameKeyDown}
            onClick={(e) => e.stopPropagation()}
            autoFocus
          />
        ) : (
          <span className="chat-thread-title">{thread.title}</span>
        )}

        {!isRenaming && (
          <div className="chat-thread-actions" onClick={(e) => e.stopPropagation()}>
            <button
              className={`chat-icon-btn${thread.pinned ? ' pinned' : ''}`}
              title={thread.pinned ? 'Unpin' : 'Pin'}
              onClick={() => onPinThread(thread.id)}
            >
              <PinIcon pinned={thread.pinned} />
            </button>
            <button className="chat-icon-btn" title="Rename" onClick={() => startRename(thread)}>
              <PencilIcon />
            </button>
            {!thread.pinned && (
              <button
                className="chat-icon-btn danger"
                title="Delete"
                onClick={() => handleDelete(thread.id, thread.title)}
              >
                <TrashIcon />
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={onCloseMobile} />
      )}

      <aside
        ref={sidebarRef}
        className={`chat-sidebar${collapsed ? ' collapsed' : ''}${mobileOpen ? ' mobile-open' : ''}`}
      >
        {/* Resize handle — only visible when not collapsed */}
        {!collapsed && (
          <div
            className="chat-sidebar-resize-handle"
            onMouseDown={handleResizeMouseDown}
            role="separator"
            aria-orientation="vertical"
          />
        )}

        {/* Header: collapse toggle + new chat */}
        <div className="chat-sidebar-header">
          <button
            className="sidebar-collapse-btn"
            onClick={toggleCollapse}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </button>

          <button
            className="new-chat-btn"
            onClick={() => {
              onNewChat()
              if (mobileOpen) onCloseMobile()
            }}
            title="New chat (Ctrl+K)"
          >
            <PlusIcon />
            <span className="new-chat-btn-label">New Chat</span>
          </button>
        </div>

        {/* Threads list */}
        <div className="chat-sidebar-threads">
          {/* Pinned section */}
          {pinned.length > 0 && (
            <>
              <div className="pinned-section-label">
                <PinIcon pinned={true} size={10} />
                Pinned
              </div>
              {pinned.map((t) => <ThreadItem key={t.id} thread={t} />)}
              <div className="threads-divider" />
            </>
          )}

          {/* Pending (unsaved) new chat — virtual item, no API call yet */}
          {hasPendingChat && (
            <div className="chat-thread-item active">
              <span className="chat-thread-dot" />
              <span className="chat-thread-title" style={{ fontStyle: 'italic', opacity: 0.85 }}>New Chat</span>
            </div>
          )}

          {/* Recent / all threads */}
          {unpinned.map((t) => <ThreadItem key={t.id} thread={t} />)}

          {threads.length === 0 && !hasPendingChat && (
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', textAlign: 'center', padding: '1.5rem 0.5rem' }}>
              No conversations yet
            </p>
          )}

          {threadsHasMore && (
            <button className="load-more-btn" onClick={onLoadMoreThreads} disabled={isLoadingMoreThreads}>
              {isLoadingMoreThreads ? 'Loading…' : 'Load more'}
            </button>
          )}
        </div>

        {/* Footer */}
        <div className="chat-sidebar-footer">
          <Link href="/documents" className="sidebar-docs-link" title="Documents">
            <FolderIcon />
            <span className="sidebar-docs-link-text">Documents</span>
          </Link>
          <Link href="/data-sources" className="sidebar-docs-link" title="Data Sources">
            <DatabaseIcon />
            <span className="sidebar-docs-link-text">Data Sources</span>
          </Link>

          <div className="sidebar-user-row">
            <Link href="/profile" className="sidebar-user-info" title="Edit profile">
              <span className="sidebar-avatar">
                {avatarSrc ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={avatarSrc} alt="" className="sidebar-avatar-img" crossOrigin="use-credentials" />
                ) : (
                  <span className="sidebar-avatar-initials">{initials}</span>
                )}
              </span>
              <span className="sidebar-user-name">{user?.name ?? '…'}</span>
            </Link>

            <button className="logout-btn" onClick={onLogout} title="Sign out">
              <LogoutIcon />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function PencilIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}

function PinIcon({ pinned, size = 13 }: { pinned: boolean; size?: number }) {
  return pinned ? (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <path d="M12 2a5 5 0 0 1 5 5c0 2.76-1.79 5.11-4.25 5.77L12 20l-.75-7.23C8.79 12.11 7 9.76 7 7a5 5 0 0 1 5-5z" />
    </svg>
  ) : (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2a5 5 0 0 1 5 5c0 2.76-1.79 5.11-4.25 5.77L12 20l-.75-7.23C8.79 12.11 7 9.76 7 7a5 5 0 0 1 5-5z" />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function DatabaseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4.03 3-9 3S3 13.66 3 12" />
      <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
    </svg>
  )
}

function LogoutIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  )
}

function ChevronLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

