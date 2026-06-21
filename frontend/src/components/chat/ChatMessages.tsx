'use client'

import { useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '@/lib/types'

// UI-only extension — isPending marks optimistic placeholders that haven't
// been confirmed by the server yet.
export type DisplayMessage = ChatMessage & { isPending?: boolean }

interface Props {
  messages: DisplayMessage[]
  isGenerating: boolean
  regeneratingId: string | null
  onEditMessage: (id: string, content: string) => void
  onRegenerateMessage: (id: string) => void
}

export default function ChatMessages({
  messages,
  isGenerating,
  regeneratingId,
  onEditMessage,
  onRegenerateMessage,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [speakingId, setSpeakingId] = useState<string | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Cancel any ongoing speech synthesis when the component unmounts or messages change.
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel()
    }
  }, [])

  function startEdit(message: DisplayMessage) {
    setEditingId(message.id)
    setEditValue(message.content)
  }

  function cancelEdit() {
    setEditingId(null)
  }

  function commitEdit() {
    if (editingId && editValue.trim()) {
      onEditMessage(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  function handleEditKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      commitEdit()
    }
    if (e.key === 'Escape') cancelEdit()
  }

  async function handleCopy(id: string, content: string) {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      // Clipboard API unavailable — silently ignore
    }
  }

  function handleSpeak(id: string, content: string) {
    if (!window.speechSynthesis) return

    if (speakingId === id) {
      window.speechSynthesis.cancel()
      setSpeakingId(null)
      return
    }

    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(content)
    utterance.onend = () => setSpeakingId(null)
    utterance.onerror = () => setSpeakingId(null)
    setSpeakingId(id)
    window.speechSynthesis.speak(utterance)
  }

  if (messages.length === 0) {
    return (
      <div className="chat-messages chat-empty-state">
        <svg
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="1.5"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <p style={{ fontSize: '0.9375rem' }}>Send a message to start the conversation</p>
      </div>
    )
  }

  return (
    <div className="chat-messages">
      {messages.map((msg) => {
        const isPending = !!msg.isPending
        const isRegenerating = msg.id === regeneratingId

        return (
          <div
            key={msg.id}
            className={`chat-message ${msg.role}${isPending ? ' pending' : ''}`}
          >
            {/* ── Pending assistant placeholder (typing animation) ── */}
            {msg.role === 'assistant' && isPending && (
              <div className="chat-bubble assistant-bubble">
                <span className="typing-dots">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            )}

            {/* ── Pending user message (optimistic, waiting for server) ── */}
            {msg.role === 'user' && isPending && (
              <div className="chat-bubble">{msg.content}</div>
            )}

            {/* ── Real messages ── */}
            {!isPending && editingId === msg.id ? (
              /* Inline edit form for user messages */
              <div style={{ width: '100%', maxWidth: 680 }}>
                <textarea
                  className="chat-textarea"
                  style={{
                    width: '100%',
                    border: '1px solid var(--color-border-focus)',
                    borderRadius: 'var(--radius)',
                    padding: '0.5rem 0.75rem',
                    background: 'var(--color-surface)',
                    resize: 'vertical',
                  }}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={handleEditKeyDown}
                  autoFocus
                />
                <div
                  style={{
                    display: 'flex',
                    gap: '0.5rem',
                    marginTop: '0.375rem',
                    justifyContent: 'flex-end',
                  }}
                >
                  <button onClick={cancelEdit} className="msg-action-btn">
                    Cancel
                  </button>
                  <button
                    onClick={commitEdit}
                    className="msg-action-btn primary"
                    disabled={isGenerating}
                  >
                    {isGenerating ? 'Saving…' : 'Save & send'}
                  </button>
                </div>
              </div>
            ) : !isPending ? (
              <>
                {/* Message bubble */}
                {msg.role === 'assistant' && isRegenerating ? (
                  <div className="chat-bubble assistant-bubble">
                    <span className="typing-dots">
                      <span />
                      <span />
                      <span />
                    </span>
                  </div>
                ) : (
                  <div className={`chat-bubble${msg.role === 'assistant' ? ' assistant-bubble' : ''}`}>
                    {msg.content}
                  </div>
                )}

                {/* Message meta row */}
                <div className="chat-message-meta">
                  {msg.edited_at && <span className="meta-tag">(edited)</span>}

                  {msg.role === 'user' && (
                    <button
                      className="meta-icon-btn"
                      title="Edit message"
                      disabled={isGenerating}
                      onClick={() => startEdit(msg)}
                    >
                      <EditIcon />
                      Edit
                    </button>
                  )}

                  {msg.role === 'assistant' && !isRegenerating && (
                    <>
                      <button
                        className="meta-icon-btn"
                        title={copiedId === msg.id ? 'Copied!' : 'Copy'}
                        onClick={() => handleCopy(msg.id, msg.content)}
                      >
                        {copiedId === msg.id ? <CheckIcon /> : <CopyIcon />}
                        {copiedId === msg.id ? 'Copied' : 'Copy'}
                      </button>

                      <button
                        className={`meta-icon-btn${speakingId === msg.id ? ' active' : ''}`}
                        title={speakingId === msg.id ? 'Stop reading' : 'Read aloud'}
                        onClick={() => handleSpeak(msg.id, msg.content)}
                      >
                        <SpeakerIcon active={speakingId === msg.id} />
                        {speakingId === msg.id ? 'Stop' : 'Read'}
                      </button>

                      <button
                        className="meta-icon-btn"
                        title="Regenerate response"
                        disabled={isGenerating}
                        onClick={() => onRegenerateMessage(msg.id)}
                      >
                        <RegenerateIcon />
                        Regenerate
                      </button>
                    </>
                  )}
                </div>
              </>
            ) : null}
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function EditIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function SpeakerIcon({ active }: { active: boolean }) {
  return active ? (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  ) : (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  )
}

function RegenerateIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
    </svg>
  )
}
