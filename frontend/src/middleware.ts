import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Routes accessible without authentication
const PUBLIC_PATHS = ['/login', '/signup', '/forgot-password', '/reset-password']

export function middleware(request: NextRequest) {
  const token = request.cookies.get('access_token')?.value
  const { pathname } = request.nextUrl

  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))

  // Unauthenticated user trying to access a protected route
  if (!token && !isPublic) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Authenticated user hitting an auth page — send them to the app
  if (token && isPublic) {
    return NextResponse.redirect(new URL('/chat', request.url))
  }

  return NextResponse.next()
}

export const config = {
  // Run on all routes except Next.js internals and static assets
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
