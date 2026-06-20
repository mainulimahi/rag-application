'use client'

import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api/client'

// Placeholder — full chat UI comes in Step 3.
export default function ChatPage() {
  const router = useRouter()

  async function handleLogout() {
    await authApi.logout()
    router.push('/login')
    router.refresh()
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
        padding: '2rem',
        textAlign: 'center',
      }}
    >
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>You&apos;re logged in!</h1>
      <p style={{ color: 'var(--color-text-muted)', maxWidth: '360px' }}>
        The chat interface is coming in Step 3. Authentication is working end-to-end.
      </p>
      <button
        onClick={handleLogout}
        style={{
          marginTop: '0.5rem',
          padding: '0.5rem 1.25rem',
          fontSize: '0.9375rem',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)',
          cursor: 'pointer',
          color: 'var(--color-text)',
        }}
      >
        Sign out
      </button>
    </div>
  )
}
