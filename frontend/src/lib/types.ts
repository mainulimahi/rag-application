// Shared TypeScript types — all API response and request shapes are defined here.
// Components must import types from this file; no inline API-response types in components.

export interface User {
  id: string
  name: string
  email: string
  profile_picture_url: string | null
  created_at: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}
