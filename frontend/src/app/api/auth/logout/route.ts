import { NextResponse } from 'next/server'

export async function POST() {
  const res = NextResponse.json({ message: 'Logged out' })
  res.cookies.set('access_token', '', { httpOnly: true, maxAge: 0, path: '/' })
  res.cookies.set('refresh_token', '', { httpOnly: true, maxAge: 0, path: '/' })
  return res
}
