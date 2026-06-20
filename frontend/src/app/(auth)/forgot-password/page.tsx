'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Alert, AuthCard, Field, SubmitButton } from '@/components/auth/AuthCard'
import { authApi } from '@/lib/api/client'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [debugLink, setDebugLink] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setDebugLink('')
    setLoading(true)
    try {
      const res = await authApi.forgotPassword(email)
      setSuccess(res.message)
      if (res.debug_reset_link) {
        setDebugLink(res.debug_reset_link)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard
      title="Reset your password"
      subtitle="Enter your email and we'll send you a reset link"
    >
      {!success ? (
        <form onSubmit={handleSubmit}>
          {error && <Alert type="error" message={error} />}
          <Field
            label="Email"
            id="email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@example.com"
            autoComplete="email"
            disabled={loading}
          />
          <SubmitButton label="Send reset link" loading={loading} />
        </form>
      ) : (
        <div>
          <Alert type="success" message={success} />
          {debugLink && (
            <div
              style={{
                marginTop: '0.75rem',
                padding: '0.75rem',
                background: '#fef9c3',
                border: '1px solid #fde047',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.8125rem',
                wordBreak: 'break-all',
              }}
            >
              <strong>Dev only — reset link:</strong>
              <br />
              <Link href={debugLink} style={{ color: 'var(--color-primary)' }}>
                {debugLink}
              </Link>
            </div>
          )}
        </div>
      )}
      <p
        style={{
          marginTop: '1.25rem',
          textAlign: 'center',
          fontSize: '0.875rem',
          color: 'var(--color-text-muted)',
        }}
      >
        <Link href="/login" style={{ fontWeight: 500 }}>
          Back to sign in
        </Link>
      </p>
    </AuthCard>
  )
}
