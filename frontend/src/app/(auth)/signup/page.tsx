'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Alert, AuthCard, Field, SubmitButton } from '@/components/auth/AuthCard'
import { authApi } from '@/lib/api/client'

export default function SignupPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      await authApi.signup(name, email, password, confirmPassword)
      router.push('/chat')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed')
    } finally {
      setLoading(false)
    }
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
