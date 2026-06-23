'use client'

import Link from 'next/link'
import { useState } from 'react'
import { Alert, AuthCard, Field, SubmitButton } from '@/components/auth/AuthCard'
import { authApi } from '@/lib/api/client'

export default function SignupPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')
  const [debugLink, setDebugLink] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const result = await authApi.signup(name, email, password, confirmPassword)
      setSuccessMessage(result.message)
      if (result.debug_verification_link) {
        setDebugLink(result.debug_verification_link)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed')
    } finally {
      setLoading(false)
    }
  }

  if (successMessage) {
    return (
      <AuthCard title="Check your email" subtitle="One more step to get started">
        <Alert type="success" message={successMessage} />
        {debugLink && (
          <p style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--color-text-muted)', wordBreak: 'break-all' }}>
            <strong>Dev link:</strong>{' '}
            <a href={debugLink} style={{ color: 'var(--color-primary)' }}>
              {debugLink}
            </a>
          </p>
        )}
        <p style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
          Didn&apos;t receive it?{' '}
          <Link href="/signup" onClick={() => { setSuccessMessage(''); setDebugLink('') }} style={{ fontWeight: 500 }}>
            Try again
          </Link>
          {' or '}
          <Link href="/login" style={{ fontWeight: 500 }}>sign in</Link>
        </p>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Create an account" subtitle="Start asking questions about your documents">
      <form onSubmit={handleSubmit}>
        {error && <Alert type="error" message={error} />}
        <Field
          label="Full name"
          id="name"
          value={name}
          onChange={setName}
          placeholder="Jane Smith"
          autoComplete="name"
          disabled={loading}
        />
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
        <Field
          label="Password"
          id="password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="At least 8 characters"
          autoComplete="new-password"
          disabled={loading}
        />
        <Field
          label="Confirm password"
          id="confirm-password"
          type="password"
          value={confirmPassword}
          onChange={setConfirmPassword}
          placeholder="••••••••"
          autoComplete="new-password"
          disabled={loading}
        />
        <SubmitButton label="Create account" loading={loading} />
      </form>
      <p
        style={{
          marginTop: '1.25rem',
          textAlign: 'center',
          fontSize: '0.875rem',
          color: 'var(--color-text-muted)',
        }}
      >
        Already have an account?{' '}
        <Link href="/login" style={{ fontWeight: 500 }}>
          Sign in
        </Link>
      </p>
    </AuthCard>
  )
}
