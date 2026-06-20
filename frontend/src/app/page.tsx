import { redirect } from 'next/navigation'

// Root route — middleware handles the actual redirect based on auth state.
// This fallback covers the edge case where middleware config doesn't match '/'.
export default function Home() {
  redirect('/login')
}
