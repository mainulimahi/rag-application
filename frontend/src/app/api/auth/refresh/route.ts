import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import type { AuthResponse } from '@/lib/types'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function POST() {
  const cookieStore = cookies()
  const refreshToken = cookieStore.get('refresh_token')?.value

  if (!refreshToken) {
    return NextResponse.json({ detail: 'No refresh token' }, { status: 401 })
  }

  const upstream = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  const data = await upstream.json()

  if (!upstream.ok) {
    // Clear stale cookies so the client is redirected to login
    const res = NextResponse.json(data, { status: upstream.status })
    res.cookies.set('access_token', '', { httpOnly: true, maxAge: 0, path: '/' })
    res.cookies.set('refresh_token', '', { httpOnly: true, maxAge: 0, path: '/' })
    return res
  }

  const { access_token, refresh_token, user } = data as AuthResponse
  const isProduction = process.env.NODE_ENV === 'production'

  const res = NextResponse.json({ user })
  res.cookies.set('access_token', access_token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: 'lax',
    path: '/',
    maxAge: 30 * 60,
  })
  res.cookies.set('refresh_token', refresh_token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: 'lax',
    path: '/',
    maxAge: 7 * 24 * 60 * 60,
  })
  return res
}
