// Server-side API client used in Next.js Route Handlers.
// Reads the httpOnly access_token cookie and forwards it as a Bearer header to the backend.
// Never import this file from client components — it uses next/headers which is server-only.

import { cookies } from 'next/headers'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const cookieStore = cookies()
  const token = cookieStore.get('access_token')?.value

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  return fetch(`${BACKEND_URL}${path}`, { ...init, headers })
}
