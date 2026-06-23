// Shared TypeScript types — all API response and request shapes are defined here.
// Components must import types from this file; no inline API-response types in components.

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface User {
  id: string
  name: string
  email: string
  profile_picture_url: string | null
  created_at: string
}

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}

export interface ChatThread {
  id: string
  user_id: string
  title: string
  pinned: boolean
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  thread_id: string
  user_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  edited_at: string | null
  sources: 'llm_only' | 'retrieval' | 'web_search' | 'both' | null
}

export interface MessagePairResponse {
  user_message: ChatMessage
  assistant_message: ChatMessage
  thread: ChatThread
}

export interface EditMessageResponse {
  updated_message: ChatMessage
  assistant_message: ChatMessage
  deleted_message_ids: string[]
}

export interface RegenerateResponse {
  assistant_message: ChatMessage
}

export interface DocumentUploadResponse {
  id: string
  filename: string
  content_type: string
  status: 'processing' | 'ready' | 'failed'
  uploaded_at: string
}

export interface DocumentListItem {
  id: string
  filename: string
  content_type: string
  status: 'processing' | 'ready' | 'failed'
  processing_error: string | null
  chunk_count: number
  uploaded_at: string
}

export interface DocumentStatusResponse {
  id: string
  status: 'processing' | 'ready' | 'failed'
  processing_error: string | null
  chunk_count: number
}

export interface UserStats {
  documents_count: number
  total_chunks: number
  responses_generated: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
}

export interface DeleteAllChatsResponse {
  deleted_count: number
}

// ── SSE streaming events ──────────────────────────────────────────────────────

export type StreamEvent =
  | { type: 'status'; content: string }
  | { type: 'token'; content: string }
  | { type: 'done'; user_message: ChatMessage; assistant_message: ChatMessage; thread: ChatThread | null }
  | { type: 'error'; content: string }
