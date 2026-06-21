// Layout for authenticated app routes.
// Middleware already redirects unauthenticated users to /login before this renders.
// Intentionally minimal — each page controls its own layout.

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
