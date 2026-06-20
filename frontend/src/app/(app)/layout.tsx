// Layout for authenticated app routes.
// Middleware already redirects unauthenticated users to /login before this renders.

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {children}
    </div>
  )
}
