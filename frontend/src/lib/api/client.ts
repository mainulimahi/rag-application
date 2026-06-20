// Client-side API utilities — all calls route through Next.js API handlers (BFF pattern).
// This file is safe to import in client components.

import type { ApiError, User } from '@/lib/types'

function extractErrorMessage(detail: ApiError['detail']): string {
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg).join(', ')
  }
  return detail
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  const data = await res.json()

  if (!res.ok) {
    const err = data as ApiError
    throw new Error(extractErrorMessage(err.detail) ?? `Request failed (${res.status})`)
  }

  return data as T
}

export const authApi = {
  signup: (name: string, email: string, password: string, confirm_password: string) =>
    apiFetch<{ user: User }>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, confirm_password }),
    }),

  login: (email: string, password: string) =>
    apiFetch<{ user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    apiFetch<{ message: string }>('/api/auth/logout', { method: 'POST' }),

  forgotPassword: (email: string) =>
    apiFetch<{ message: string; debug_reset_link?: string }>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, new_password: string) =>
    apiFetch<{ message: string }>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),

  me: () => apiFetch<{ user: User }>('/api/auth/me'),
}
