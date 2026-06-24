// Centralized API client — all calls go directly to the FastAPI backend.
// credentials: 'include' is required so the browser sends httpOnly auth cookies.

import type {
  ApiError,
  ChatMessage,
  ChatThread,
  DataFile,
  DataFileStatus,
  DataSource,
  DeleteAllChatsResponse,
  DocumentListItem,
  DocumentStatusResponse,
  DocumentUploadResponse,
  EditMessageResponse,
  MessagePairResponse,
  PaginatedResponse,
  RegenerateResponse,
  StreamEvent,
  TestConnectionResult,
  User,
  UserStats,
} from '@/lib/types'

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

function extractErrorMessage(detail: ApiError['detail']): string {
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg).join(', ')
  }
  return detail
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers as Record<string, string> | undefined),
    },
  })

  const text = await res.text()
  let data: unknown
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    throw new Error(text || `Request failed (${res.status})`)
  }

  if (!res.ok) {
    const err = data as ApiError | null
    const detail = err?.detail
    throw new Error(
      detail != null ? extractErrorMessage(detail) : `Request failed (${res.status})`,
    )
  }

  return data as T
}

export const usersApi = {
  me: () => apiFetch<User>('/api/users/me'),

  updateName: (name: string) =>
    apiFetch<User>('/api/users/me', {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),

  changePassword: (current_password: string, new_password: string, confirm_new_password: string) =>
    apiFetch<{ message: string }>('/api/users/me/password', {
      method: 'PATCH',
      body: JSON.stringify({ current_password, new_password, confirm_new_password }),
    }),

  deleteAccount: async (password: string): Promise<void> => {
    const res = await fetch(`${API_URL}/api/users/me`, {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!res.ok) {
      const data = (await res.json()) as ApiError
      throw new Error(
        data?.detail != null
          ? typeof data.detail === 'string'
            ? data.detail
            : data.detail.map((e) => e.msg).join(', ')
          : `Request failed (${res.status})`,
      )
    }
  },

  stats: () => apiFetch<UserStats>('/api/users/me/stats'),

  uploadAvatar: async (file: File): Promise<User> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_URL}/api/users/me/avatar`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    })
    const text = await res.text()
    let data: unknown
    try {
      data = text ? JSON.parse(text) : null
    } catch {
      throw new Error(text || `Upload failed (${res.status})`)
    }
    if (!res.ok) {
      const err = data as ApiError | null
      const detail = err?.detail
      throw new Error(
        detail != null ? extractErrorMessage(detail) : `Upload failed (${res.status})`,
      )
    }
    return data as User
  },
}

export const authApi = {
  signup: (name: string, email: string, password: string, confirm_password: string) =>
    apiFetch<{ message: string; debug_verification_link?: string }>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, confirm_password }),
    }),

  verifyEmail: (token: string) =>
    apiFetch<{ message: string }>(`/api/auth/verify-email?token=${encodeURIComponent(token)}`, {
      method: 'POST',
    }),

  resendVerification: (email: string) =>
    apiFetch<{ message: string }>('/api/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  login: (email: string, password: string) =>
    apiFetch<User>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    apiFetch<{ message: string }>('/api/auth/logout', { method: 'POST' }),

  forgotPassword: (email: string) =>
    apiFetch<{ message: string; debug_reset_link?: string }>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, new_password: string) =>
    apiFetch<{ message: string }>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),

  me: () => apiFetch<User>('/api/users/me'),
}

export const chatApi = {
  listThreads: (page = 1, limit = 20) =>
    apiFetch<PaginatedResponse<ChatThread>>(`/api/chat-threads?page=${page}&limit=${limit}`),

  createThread: (title?: string) =>
    apiFetch<ChatThread>('/api/chat-threads', {
      method: 'POST',
      body: JSON.stringify({ title: title ?? 'New Chat' }),
    }),

  renameThread: (threadId: string, title: string) =>
    apiFetch<ChatThread>(`/api/chat-threads/${threadId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  pinThread: (threadId: string) =>
    apiFetch<ChatThread>(`/api/chat-threads/${threadId}/pin`, { method: 'PATCH' }),

  deleteThread: async (threadId: string): Promise<void> => {
    const res = await fetch(`${API_URL}/api/chat-threads/${threadId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const data = (await res.json()) as ApiError
      throw new Error(extractErrorMessage(data.detail) ?? `Request failed (${res.status})`)
    }
  },

  deleteAllChats: async (password: string): Promise<DeleteAllChatsResponse> => {
    const res = await fetch(`${API_URL}/api/chat-threads`, {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!res.ok) {
      const data = (await res.json()) as ApiError
      throw new Error(
        data?.detail != null ? extractErrorMessage(data.detail) : `Request failed (${res.status})`
      )
    }
    return res.json() as Promise<DeleteAllChatsResponse>
  },

  listMessages: (threadId: string, page = 1, limit = 50) =>
    apiFetch<PaginatedResponse<ChatMessage>>(
      `/api/chat-threads/${threadId}/messages?page=${page}&limit=${limit}`
    ),

  createMessage: (threadId: string, content: string) =>
    apiFetch<MessagePairResponse>(`/api/chat-threads/${threadId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  /** Consume the SSE stream. Yields parsed StreamEvent objects. */
  async *streamMessage(threadId: string, content: string): AsyncGenerator<StreamEvent> {
    const res = await fetch(`${API_URL}/api/chat-threads/${threadId}/messages/stream`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })

    if (!res.ok || !res.body) {
      throw new Error(`Stream request failed (${res.status})`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const json = line.slice(6).trim()
          if (json) {
            yield JSON.parse(json) as StreamEvent
          }
        }
      }
    }
  },

  updateMessage: (messageId: string, content: string) =>
    apiFetch<EditMessageResponse>(`/api/chat-messages/${messageId}`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),

  regenerateMessage: (messageId: string) =>
    apiFetch<RegenerateResponse>(`/api/chat-messages/${messageId}/regenerate`, {
      method: 'POST',
    }),
}

export const dataFilesApi = {
  upload: async (file: File): Promise<DataFile> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_URL}/api/data-files/upload`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    })
    const text = await res.text()
    let data: unknown
    try {
      data = text ? JSON.parse(text) : null
    } catch {
      throw new Error(text || `Upload failed (${res.status})`)
    }
    if (!res.ok) {
      const err = data as ApiError | null
      const detail = err?.detail
      throw new Error(
        detail != null ? extractErrorMessage(detail) : `Upload failed (${res.status})`,
      )
    }
    return data as DataFile
  },

  list: () => apiFetch<DataFile[]>('/api/data-files'),

  getSchema: (fileId: string) => apiFetch<DataFile>(`/api/data-files/${fileId}/schema`),

  getStatus: (fileId: string) => apiFetch<DataFileStatus>(`/api/data-files/${fileId}/status`),

  delete: async (fileId: string): Promise<void> => {
    const res = await fetch(`${API_URL}/api/data-files/${fileId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const data = (await res.json()) as ApiError
      throw new Error(
        data?.detail != null ? extractErrorMessage(data.detail) : `Delete failed (${res.status})`,
      )
    }
  },
}

export const dataSourcesApi = {
  list: () => apiFetch<DataSource[]>('/api/data-sources'),

  create: (data: { name: string; source_type: string; connection_config: Record<string, unknown> }) =>
    apiFetch<DataSource>('/api/data-sources', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: { name?: string; connection_config?: Record<string, unknown> }) =>
    apiFetch<DataSource>(`/api/data-sources/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: async (id: string): Promise<void> => {
    const res = await fetch(`${API_URL}/api/data-sources/${id}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const data = (await res.json()) as ApiError
      throw new Error(
        data?.detail != null ? extractErrorMessage(data.detail) : `Delete failed (${res.status})`,
      )
    }
  },

  test: (id: string) =>
    apiFetch<TestConnectionResult>(`/api/data-sources/${id}/test`, { method: 'POST' }),
}

export const documentApi = {
  upload: async (file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_URL}/api/documents/upload`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    })
    const text = await res.text()
    let data: unknown
    try {
      data = text ? JSON.parse(text) : null
    } catch {
      throw new Error(text || `Upload failed (${res.status})`)
    }
    if (!res.ok) {
      const err = data as ApiError | null
      const detail = err?.detail
      throw new Error(
        detail != null
          ? Array.isArray(detail)
            ? detail.map((e) => e.msg).join(', ')
            : detail
          : `Upload failed (${res.status})`,
      )
    }
    return data as DocumentUploadResponse
  },

  list: (page = 1, limit = 20) =>
    apiFetch<PaginatedResponse<DocumentListItem>>(`/api/documents?page=${page}&limit=${limit}`),

  getStatus: (documentId: string) =>
    apiFetch<DocumentStatusResponse>(`/api/documents/${documentId}/status`),

  delete: async (documentId: string): Promise<void> => {
    const res = await fetch(`${API_URL}/api/documents/${documentId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const data = (await res.json()) as ApiError
      throw new Error(
        data?.detail != null
          ? Array.isArray(data.detail)
            ? data.detail.map((e) => e.msg).join(', ')
            : data.detail
          : `Delete failed (${res.status})`,
      )
    }
  },
}
