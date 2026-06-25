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

export interface DataAnalysisResult {
  sql: string
  columns: string[]
  rows: unknown[][]
  row_count: number
  total_row_count: number
  truncated: boolean
  summary_stats: Record<string, Record<string, unknown>>
  sources_used: Array<{ name: string; type: string }>
  error?: string
  message?: string
}

export interface ChatMessage {
  id: string
  thread_id: string
  user_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  edited_at: string | null
  sources: 'llm_only' | 'retrieval' | 'web_search' | 'both' | 'data_analysis' | null
  data_analysis?: DataAnalysisResult | null
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

// ── Data Sources (v2) ─────────────────────────────────────────────────────────

export type DataSourceType =
  | 'postgresql'
  | 'mysql'
  | 'sqlite'
  | 's3'
  | 'gcs'
  | 'azure_blob'
  | 'api'

export interface DataSource {
  id: string
  name: string
  source_type: DataSourceType
  last_tested_at: string | null
  last_test_status: 'ok' | 'error' | null
  last_test_error: string | null
  created_at: string
  updated_at: string
  schema_cache?: Record<string, unknown> | null
}

export interface TestConnectionResult {
  status: 'ok' | 'error'
  message: string
  tables_found?: number | null
  schema_summary?: Record<string, unknown> | null
}

export interface DataFileSchemaColumn {
  column_name: string
  column_type: string
  sample_values?: unknown[] | null
  null_count?: number | null
  unique_count?: number | null
}

export interface DataFile {
  id: string
  filename: string
  file_size: number
  content_type: string
  status: 'processing' | 'ready' | 'failed'
  processing_error: string | null
  row_count: number | null
  column_count: number
  uploaded_at: string
  columns?: DataFileSchemaColumn[]
}

export interface DataFileStatus {
  id: string
  status: 'processing' | 'ready' | 'failed'
  processing_error: string | null
  row_count: number | null
  column_count: number
}

// ── SSE streaming events ──────────────────────────────────────────────────────

export type StreamEvent =
  | { type: 'status'; content: string }
  | { type: 'token'; content: string }
  | { type: 'done'; user_message: ChatMessage; assistant_message: ChatMessage; thread: ChatThread | null; data_analysis?: DataAnalysisResult | null }
  | { type: 'error'; content: string }
