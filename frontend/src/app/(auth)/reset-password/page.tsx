'use client'

import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useState } from 'react'
import { Alert, AuthCard, Field, SubmitButton } from '@/components/auth/AuthCard'
import { authApi } from '@/lib/api/client'

function ResetPasswordForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  if (!token) {
    return <Alert type="error" message="Invalid reset link. Please request a new one." />
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const res = await authApi.resetPassword(token, password)
      setSuccess(res.message)
      setTimeout(() => router.push('/login'), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Password reset failed')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <>
        <Alert type="success" message={success} />
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Redirecting to sign in…
        </p>
      </>
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      {error && <Alert type="error" message={error} />}
      <Field
        label="New password"
        id="password"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="At least 8 characters"
        autoComplete="new-password"
        disabled={loading}
      />
      <Field
        label="Confirm new password"
        id="confirm-password"
        type="password"
        value={confirmPassword}
        onChange={setConfirmPassword}
        placeholder="••••••••"
        autoComplete="new-password"
        disabled={loading}
      />
      <SubmitButton label="Reset password" loading={loading} />
    </form>
  )
}

export default function ResetPasswordPage() {
  return (
    <AuthCard title="Set a new password" subtitle="Choose a password with at least 8 characters">
      <Suspense fallback={<p style={{ color: 'var(--color-text-muted)' }}>Loading…</p>}>
        <ResetPasswordForm />
      </Suspense>
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
