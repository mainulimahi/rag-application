'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useRef, useState } from 'react'
import { Alert, AuthCard } from '@/components/auth/AuthCard'
import { authApi } from '@/lib/api/client'

function VerifyEmailContent() {
  const router = useRouter()
  const params = useSearchParams()
  const token = params.get('token') ?? ''

  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying')
  const [message, setMessage] = useState('')
  const attempted = useRef(false)

  useEffect(() => {
    if (attempted.current) return
    attempted.current = true

    if (!token) {
      setStatus('error')
      setMessage('No verification token found. Please use the link from your email.')
      return
    }

    authApi.verifyEmail(token)
      .then(() => {
        setStatus('success')
        setMessage('Email verified! Redirecting you to the app…')
        setTimeout(() => router.push('/chat'), 1500)
      })
      .catch((err: unknown) => {
        setStatus('error')
        setMessage(err instanceof Error ? err.message : 'Verification failed. The link may have expired.')
      })
  }, [token, router])

  if (status === 'verifying') {
    return (
      <AuthCard title="Verifying your email" subtitle="Just a moment…">
        <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: '1rem 0' }}>
          Verifying your email address…
        </p>
      </AuthCard>
    )
  }

  if (status === 'success') {
    return (
      <AuthCard title="Email verified!" subtitle="Welcome to RAG Application">
        <Alert type="success" message={message} />
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Verification failed" subtitle="Something went wrong">
      <Alert type="error" message={message} />
      <p style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
        <Link href="/login" style={{ fontWeight: 500 }}>Back to sign in</Link>
        {' · '}
        <Link href="/signup" style={{ fontWeight: 500 }}>Create new account</Link>
      </p>
    </AuthCard>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <AuthCard title="Verifying your email" subtitle="Just a moment…">
        <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: '1rem 0' }}>
          Loading…
        </p>
      </AuthCard>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}
