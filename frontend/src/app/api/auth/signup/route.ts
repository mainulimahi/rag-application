import { NextResponse } from 'next/server'
import type { AuthResponse } from '@/lib/types'

const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export async function POST(request: Request) {
  const body = await request.json()

  const upstream = await fetch(`${BACKEND_URL}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  const data = await upstream.json()

  if (!upstream.ok) {
    return NextResponse.json(data, { status: upstream.status })
  }

  const { access_token, refresh_token, user } = data as AuthResponse
  const isProduction = process.env.NODE_ENV === 'production'

  const res = NextResponse.json({ user }, { status: 201 })
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
