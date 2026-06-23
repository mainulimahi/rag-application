'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Alert, AuthCard, Field, SubmitButton } from '@/components/auth/AuthCard'
import { authApi } from '@/lib/api/client'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [unverified, setUnverified] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [resendSuccess, setResendSuccess] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setUnverified(false)
    setResendSuccess('')
    setLoading(true)
    try {
      await authApi.login(email, password)
      router.push('/chat')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      if (msg.toLowerCase().includes('verify')) {
        setUnverified(true)
        setError(msg)
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleResendVerification() {
    if (!email) return
    setResendLoading(true)
    setResendSuccess('')
    try {
      await authApi.resendVerification(email)
      setResendSuccess('Verification email sent — check your inbox.')
    } catch {
      setResendSuccess('Failed to resend. Please try again.')
    } finally {
      setResendLoading(false)
    }
  }

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to your account">
      <form onSubmit={handleSubmit}>
        {error && <Alert type="error" message={error} />}
        {resendSuccess && <Alert type="success" message={resendSuccess} />}
        {unverified && !resendSuccess && (
          <div style={{ marginBottom: '1rem', fontSize: '0.875rem', textAlign: 'center' }}>
            <button
              type="button"
              onClick={handleResendVerification}
              disabled={resendLoading || !email}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary)',
                cursor: 'pointer',
                textDecoration: 'underline',
                fontSize: 'inherit',
                padding: 0,
              }}
            >
              {resendLoading ? 'Sending…' : 'Resend verification email'}
            </button>
          </div>
        )}
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
          placeholder="••••••••"
          autoComplete="current-password"
          disabled={loading}
        />
        <div style={{ textAlign: 'right', marginBottom: '1rem', marginTop: '-0.5rem' }}>
          <Link href="/forgot-password" style={{ fontSize: '0.8125rem' }}>
            Forgot password?
          </Link>
        </div>
        <SubmitButton label="Sign in" loading={loading} />
      </form>
      <p
        style={{
          marginTop: '1.25rem',
          textAlign: 'center',
          fontSize: '0.875rem',
          color: 'var(--color-text-muted)',
        }}
      >
        Don&apos;t have an account?{' '}
        <Link href="/signup" style={{ fontWeight: 500 }}>
          Sign up
        </Link>
      </p>
    </AuthCard>
  )
}
