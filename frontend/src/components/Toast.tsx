'use client'

import { useEffect, useState } from 'react'

export type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: string
  message: string
  type: ToastType
  exiting?: boolean
}

// Module-level pub/sub — any component can call showToast() without needing context.
type Listener = (toast: Omit<Toast, 'exiting'>) => void
const _listeners = new Set<Listener>()

export function showToast(message: string, type: ToastType = 'info') {
  const toast = { id: Math.random().toString(36).slice(2), message, type }
  _listeners.forEach((fn) => fn(toast))
}

const DURATION_MS = 3200
const EXIT_MS = 180

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    const listener: Listener = (toast) => {
      setToasts((prev) => [...prev, toast])

      // Start exit animation before removal
      setTimeout(() => {
        setToasts((prev) =>
          prev.map((t) => (t.id === toast.id ? { ...t, exiting: true } : t))
        )
      }, DURATION_MS - EXIT_MS)

      // Remove after animation
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id))
      }, DURATION_MS)
    }

    _listeners.add(listener)
    return () => {
      _listeners.delete(listener)
    }
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="toast-container" role="region" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type}${toast.exiting ? ' exiting' : ''}`}
          role="status"
        >
          <ToastIcon type={toast.type} />
          {toast.message}
        </div>
      ))}
    </div>
  )
}

function ToastIcon({ type }: { type: ToastType }) {
  if (type === 'success') {
    return (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
        <polyline points="20 6 9 17 4 12" />
      </svg>
    )
  }
  if (type === 'error') {
    return (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
        <circle cx="12" cy="12" r="10" />
        <line x1="15" y1="9" x2="9" y2="15" />
        <line x1="9" y1="9" x2="15" y2="15" />
      </svg>
    )
  }
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}
