import { NextResponse } from 'next/server'
import { backendFetch } from '@/lib/api/server'
import type { User } from '@/lib/types'

export async function GET() {
  const upstream = await backendFetch('/api/users/me')
  const data = await upstream.json()

  if (!upstream.ok) {
    return NextResponse.json(data, { status: upstream.status })
  }

  return NextResponse.json({ user: data as User })
}
