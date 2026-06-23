'use client'

import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage } from '@/lib/types'

export type DisplayMessage = ChatMessage & {
  isPending?: boolean
  isStreaming?: boolean
}

const SUGGESTED_PROMPTS = [
  { icon: '📄', text: 'Summarize my uploaded documents' },
  { icon: '🔍', text: 'What topics do my documents cover?' },
  { icon: '🌐', text: 'Search the web for the latest AI news' },
  { icon: '💡', text: 'What can you help me with?' },
]

interface Props {
  messages: DisplayMessage[]
  isGenerating: boolean
  streamingStatus: string
  regeneratingId: string | null
  messagesHasOlder: boolean
  isLoadingOlder: boolean
  isLoadingMessages: boolean
  onEditMessage: (id: string, content: string) => void
  onRegenerateMessage: (id: string) => void
  onLoadOlderMessages: () => void
  onSuggestedPrompt: (text: string) => void
}

export default function ChatMessages({
  messages,
  isGenerating,
  streamingStatus,
  regeneratingId,
  messagesHasOlder,
  isLoadingOlder,
  isLoadingMessages,
  onEditMessage,
  onRegenerateMessage,
  onLoadOlderMessages,
  onSuggestedPrompt,
}: Props) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [showScrollBtn, setShowScrollBtn] = useState(false)

  // Scroll to bottom when new messages arrive (only if already near bottom)
  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    if (distFromBottom < 200) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Track scroll position to show/hide the scroll-to-bottom button
  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return
    function onScroll() {
      const dist = el!.scrollHeight - el!.scrollTop - el!.clientHeight
      setShowScrollBtn(dist > 300)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  function scrollToBottom() {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

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
      // Clipboard unavailable
    }
  }

  // ── Loading skeleton ────────────────────────────────────────────────────────

  if (isLoadingMessages) {
    return (
      <div className="chat-messages" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div className="skeleton skeleton-message-user" />
        <div className="skeleton skeleton-message-assistant" />
        <div className="skeleton skeleton-message-user" style={{ width: '40%' }} />
        <div className="skeleton skeleton-message-assistant" style={{ height: '6rem' }} />
      </div>
    )
  }

  // ── Empty state ─────────────────────────────────────────────────────────────

  if (messages.length === 0 && !isGenerating) {
    return (
      <div className="chat-messages chat-empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-border)" strokeWidth="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <p style={{ fontSize: '0.9375rem', color: 'var(--color-text-muted)', marginTop: '0.75rem' }}>
          Ask anything — your documents and the web are available as context
        </p>
        <div className="chat-empty-prompts">
          {SUGGESTED_PROMPTS.map((p) => (
            <button
              key={p.text}
              className="chat-empty-prompt-btn"
              onClick={() => onSuggestedPrompt(p.text)}
            >
              <span className="chat-empty-prompt-icon">{p.icon}</span>
              <span>{p.text}</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // ── Message list ────────────────────────────────────────────────────────────

  return (
    <div className="chat-messages" ref={scrollContainerRef}>
      {messagesHasOlder && (
        <div style={{ textAlign: 'center', padding: '0.5rem 0' }}>
          <button
            className="load-more-btn"
            onClick={onLoadOlderMessages}
            disabled={isLoadingOlder}
          >
            {isLoadingOlder ? 'Loading…' : 'Load older messages'}
          </button>
        </div>
      )}

      {messages.map((msg) => {
        const isPending = !!msg.isPending
        const isStreaming = !!msg.isStreaming
        const isRegenerating = msg.id === regeneratingId

        return (
          <div
            key={msg.id}
            className={`chat-message ${msg.role}${isPending ? ' pending' : ''}`}
          >
            {/* ── Pending assistant: show streaming status + content or dots ── */}
            {msg.role === 'assistant' && isPending && (
              <>
                {streamingStatus && !isStreaming && (
                  <div className="streaming-status">
                    <span className="streaming-status-pulse" />
                    {streamingStatus}
                  </div>
                )}
                {isStreaming && streamingStatus && (
                  <div className="streaming-status">
                    <span className="streaming-status-pulse" />
                    {streamingStatus}
                  </div>
                )}
                <div className="chat-bubble assistant-bubble">
                  {isStreaming && msg.content ? (
                    <div className="md-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {msg.content}
                      </ReactMarkdown>
                      <span className="streaming-cursor" aria-hidden="true" />
                    </div>
                  ) : (
                    <span className="typing-dots">
                      <span />
                      <span />
                      <span />
                    </span>
                  )}
                </div>
              </>
            )}

            {/* ── Pending user: optimistic display ── */}
            {msg.role === 'user' && isPending && (
              <div className="chat-bubble">{msg.content}</div>
            )}

            {/* ── Real messages ── */}
            {!isPending && editingId === msg.id ? (
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
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.375rem', justifyContent: 'flex-end' }}>
                  <button onClick={cancelEdit} className="msg-action-btn">Cancel</button>
                  <button onClick={commitEdit} className="msg-action-btn primary" disabled={isGenerating}>
                    {isGenerating ? 'Saving…' : 'Save & send'}
                  </button>
                </div>
              </div>
            ) : !isPending ? (
              <>
                {/* Bubble */}
                {msg.role === 'assistant' && isRegenerating ? (
                  <div className="chat-bubble assistant-bubble">
                    <span className="typing-dots"><span /><span /><span /></span>
                  </div>
                ) : (
                  <div className={`chat-bubble${msg.role === 'assistant' ? ' assistant-bubble' : ''}`}>
                    {msg.role === 'assistant' ? (
                      <div className="md-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      msg.content
                    )}
                  </div>
                )}

                {/* Source badge */}
                {msg.role === 'assistant' && !isRegenerating && msg.sources && msg.sources !== 'llm_only' && (
                  <div className="source-badge">
                    {msg.sources === 'retrieval' && '📄 From your documents'}
                    {msg.sources === 'web_search' && '🌐 Web search'}
                    {msg.sources === 'both' && '📄🌐 Documents + Web'}
                  </div>
                )}

                {/* Meta row */}
                <div className="chat-message-meta">
                  {msg.edited_at && <span className="meta-tag">(edited)</span>}

                  {msg.role === 'user' && (
                    <button className="meta-icon-btn" title="Edit message" disabled={isGenerating} onClick={() => startEdit(msg)}>
                      <EditIcon /> Edit
                    </button>
                  )}

                  {msg.role === 'assistant' && !isRegenerating && (
                    <>
                      <button className="meta-icon-btn" title={copiedId === msg.id ? 'Copied!' : 'Copy'} onClick={() => handleCopy(msg.id, msg.content)}>
                        {copiedId === msg.id ? <CheckIcon /> : <CopyIcon />}
                        {copiedId === msg.id ? 'Copied' : 'Copy'}
                      </button>
                      <button className="meta-icon-btn" title="Regenerate response" disabled={isGenerating} onClick={() => onRegenerateMessage(msg.id)}>
                        <RegenerateIcon /> Regenerate
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

      {showScrollBtn && (
        <button className="scroll-to-bottom" onClick={scrollToBottom} title="Scroll to bottom" aria-label="Scroll to bottom">
          <ChevronDownIcon />
        </button>
      )}
    </div>
  )
}

// ── Shared ReactMarkdown components ───────────────────────────────────────────

const mdComponents = {
  // react-markdown v10 passes children as optional in ExtraProps
  pre({ children }: { children?: React.ReactNode }) {
    return <CodeBlock>{children}</CodeBlock>
  },
  code({ children, className }: { children?: React.ReactNode; className?: string }) {
    if (!className) return <code className="md-inline-code">{children}</code>
    return <code className={className}>{children}</code>
  },
}

// ── Code block with copy ──────────────────────────────────────────────────────

function CodeBlock({ children }: { children: React.ReactNode }) {
  const [copied, setCopied] = useState(false)

  function getLang(node: React.ReactNode): string {
    if (node && typeof node === 'object' && 'props' in (node as object)) {
      const className: string = (node as React.ReactElement).props?.className ?? ''
      const match = className.match(/language-(\w+)/)
      return match?.[1] ?? ''
    }
    return ''
  }

  function getTextContent(node: React.ReactNode): string {
    if (typeof node === 'string') return node
    if (typeof node === 'number') return String(node)
    if (Array.isArray(node)) return node.map(getTextContent).join('')
    if (node && typeof node === 'object' && 'props' in (node as object)) {
      return getTextContent((node as React.ReactElement).props.children)
    }
    return ''
  }

  async function handleCopy() {
    const text = getTextContent(children)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* ignore */ }
  }

  const lang = getLang(Array.isArray(children) ? children[0] : children)

  return (
    <div className="md-code-block">
      {lang && <span className="md-code-lang">{lang}</span>}
      <button className="md-code-copy" onClick={handleCopy} title="Copy code"
        style={lang ? { left: 'auto' } : undefined}>
        {copied ? <CheckIcon /> : <CopyIcon />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre>{children}</pre>
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

function RegenerateIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.51" />
    </svg>
  )
}

function ChevronDownIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}
