'use client'

import Link from 'next/link'
import { useRef, useState } from 'react'
import { API_URL } from '@/lib/api/client'
import type { ChatThread, User } from '@/lib/types'

interface Props {
  threads: ChatThread[]
  selectedThreadId: string | null
  user: User | null
  threadsHasMore: boolean
  isLoadingMoreThreads: boolean
  onSelectThread: (id: string) => void
  onNewChat: () => void
  onRenameThread: (id: string, title: string) => void
  onDeleteThread: (id: string) => void
  onLoadMoreThreads: () => void
  onLogout: () => void
}

export default function ChatSidebar({
  threads,
  selectedThreadId,
  user,
  threadsHasMore,
  isLoadingMoreThreads,
  onSelectThread,
  onNewChat,
  onRenameThread,
  onDeleteThread,
  onLoadMoreThreads,
  onLogout,
}: Props) {
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const renameInputRef = useRef<HTMLInputElement>(null)

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

  const initials = user
    ? user.name
        .split(' ')
        .map((w) => w[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?'

  const avatarSrc = user?.profile_picture_url
    ? `${API_URL}${user.profile_picture_url}`
    : null

  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar-header">
        <button className="new-chat-btn" onClick={onNewChat}>
          <PlusIcon />
          New Chat
        </button>
      </div>

      <div className="chat-sidebar-threads">
        {threads.map((thread) => (
          <div
            key={thread.id}
            className={`chat-thread-item${selectedThreadId === thread.id ? ' active' : ''}`}
            onClick={() => {
              if (renamingId !== thread.id) onSelectThread(thread.id)
            }}
          >
            {renamingId === thread.id ? (
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

            <div className="chat-thread-actions" onClick={(e) => e.stopPropagation()}>
              <button
                className="chat-icon-btn"
                title="Rename"
                onClick={() => startRename(thread)}
              >
                <PencilIcon />
              </button>
              <button
                className="chat-icon-btn danger"
                title="Delete"
                onClick={() => handleDelete(thread.id, thread.title)}
              >
                <TrashIcon />
              </button>
            </div>
          </div>
        ))}

        {threads.length === 0 && (
          <p
            style={{
              fontSize: '0.8125rem',
              color: 'var(--color-text-muted)',
              textAlign: 'center',
              padding: '1.5rem 0.5rem',
            }}
          >
            No conversations yet
          </p>
        )}

        {threadsHasMore && (
          <button
            className="load-more-btn"
            onClick={onLoadMoreThreads}
            disabled={isLoadingMoreThreads}
          >
            {isLoadingMoreThreads ? 'Loading…' : 'Load more'}
          </button>
        )}
      </div>

      <div className="chat-sidebar-footer">
        <Link href="/documents" className="sidebar-docs-link">
          <FolderIcon />
          Documents
        </Link>

        {/* User row: avatar + name + profile link */}
        <div className="sidebar-user-row">
          <Link href="/profile" className="sidebar-user-info" title="Edit profile">
            <span className="sidebar-avatar">
              {avatarSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={avatarSrc}
                  alt=""
                  className="sidebar-avatar-img"
                  crossOrigin="use-credentials"
                />
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
  )
}

function FolderIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
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

function LogoutIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  )
}
