// Centralized API client — all calls go directly to the FastAPI backend.
// NEXT_PUBLIC_API_URL is the backend base URL visible from the browser.
// credentials: 'include' is required so the browser sends httpOnly auth cookies.

import type {
  ApiError,
  ChatMessage,
  ChatThread,
  DocumentListItem,
  DocumentStatusResponse,
  DocumentUploadResponse,
  EditMessageResponse,
  MessagePairResponse,
  RegenerateResponse,
  User,
} from '@/lib/types'

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

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
    apiFetch<User>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, confirm_password }),
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
  listThreads: () => apiFetch<ChatThread[]>('/api/chat-threads'),

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

  listMessages: (threadId: string) =>
    apiFetch<ChatMessage[]>(`/api/chat-threads/${threadId}/messages`),

  createMessage: (threadId: string, content: string) =>
    apiFetch<MessagePairResponse>(`/api/chat-threads/${threadId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

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

export const documentApi = {
  upload: async (file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    // No Content-Type header — browser sets multipart/form-data with boundary automatically.
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

  list: () => apiFetch<DocumentListItem[]>('/api/documents'),

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
