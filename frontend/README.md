# Frontend

Next.js 14 frontend for the RAG application. Built with the App Router, TypeScript strict mode, and no component libraries — all UI is custom CSS via `globals.css`.

## Architecture

```
src/
├── app/
│   ├── (app)/           Authenticated pages (chat, documents, profile)
│   ├── (auth)/          Unauthenticated pages (login, signup, etc.)
│   ├── globals.css      All styles — custom properties + component styles
│   ├── layout.tsx       Root layout
│   └── page.tsx         Root route → redirects to /login
├── components/
│   ├── auth/            AuthCard shared form primitives
│   ├── chat/            ChatSidebar, ChatMessages, ChatInput
│   └── documents/       DocumentsPanel
└── lib/
    ├── api/client.ts    Centralized API client
    └── types.ts         All shared TypeScript types
```

Route protection is handled by `src/middleware.ts` — unauthenticated requests to app routes are redirected to `/login`.

## Page / Route Map

| URL | File | Access | Description |
|---|---|---|---|
| `/` | `app/page.tsx` | Public | Redirects to `/login` |
| `/login` | `app/(auth)/login/page.tsx` | Public | Email + password login; shows resend-verification flow on 403 |
| `/signup` | `app/(auth)/signup/page.tsx` | Public | Registration form; shows success message with optional dev verification link |
| `/verify-email` | `app/(auth)/verify-email/page.tsx` | Public | Auto-verifies token from URL query param; redirects to `/chat` on success |
| `/forgot-password` | `app/(auth)/forgot-password/page.tsx` | Public | Requests password reset email |
| `/reset-password` | `app/(auth)/reset-password/page.tsx` | Public | Sets new password using token from URL; redirects to `/login` |
| `/chat` | `app/(app)/chat/page.tsx` | Auth required | Main chat interface: sidebar + message list + input |
| `/documents` | `app/(app)/documents/page.tsx` | Auth required | Document management: upload, status polling, delete |
| `/profile` | `app/(app)/profile/page.tsx` | Auth required | Name edit, avatar upload, password change, account deletion |

## Components

### `components/auth/AuthCard.tsx`

Shared primitives for all auth pages:
- `AuthCard` — centered card layout with title and subtitle
- `Field` — labelled input with consistent styling
- `SubmitButton` — primary submit button with loading state
- `Alert` — inline error or success message (`type="error" | "success"`)

### `components/chat/ChatSidebar.tsx`

Left sidebar listing all chat threads. Each item has inline rename (click-to-edit) and delete (with confirmation). Bottom row shows the current user's avatar + name and a logout button. Links to the Documents page.

### `components/chat/ChatMessages.tsx`

Message list with:
- Markdown rendering (`react-markdown` + `remark-gfm`) for assistant messages
- Code blocks with a copy button
- Typing animation during streaming wait
- Per-message actions: copy raw text, read aloud (Web Speech API), regenerate, edit
- Source badges on assistant messages (`Documents`, `Web`, `Documents + Web`, or nothing for `llm_only`)
- Optimistic UI during send/edit/regenerate (pending state shown before the response arrives)

### `components/chat/ChatInput.tsx`

Auto-growing textarea. Enter sends, Shift+Enter inserts a newline. Disabled while a response is pending.

### `components/documents/DocumentsPanel.tsx`

- Drag-and-drop upload zone (also has a click-to-browse fallback)
- Client-side validation before upload: checks MIME type and file size (25 MB limit matches nginx)
- Polls `GET /api/documents/{id}/status` every 2.5 seconds while a document is in `processing` state
- Paginated document list (20 per page) with chunk count and delete button

## API Client

All API calls are in `src/lib/api/client.ts`. Components never call `fetch` directly.

The base URL is `process.env.NEXT_PUBLIC_API_URL ?? ''`. In production (Docker + nginx) this is an empty string, making all calls relative (`/api/...`) so nginx can proxy them. In local dev without Docker, set `NEXT_PUBLIC_API_URL=http://localhost:8000`.

### `authApi`

| Function | Method | Path |
|---|---|---|
| `signup(name, email, password, confirm_password)` | POST | `/api/auth/signup` |
| `verifyEmail(token)` | POST | `/api/auth/verify-email?token=...` |
| `resendVerification(email)` | POST | `/api/auth/resend-verification` |
| `login(email, password)` | POST | `/api/auth/login` |
| `logout()` | POST | `/api/auth/logout` |
| `forgotPassword(email)` | POST | `/api/auth/forgot-password` |
| `resetPassword(token, new_password)` | POST | `/api/auth/reset-password` |

### `usersApi`

| Function | Method | Path |
|---|---|---|
| `me()` | GET | `/api/users/me` |
| `updateName(name)` | PATCH | `/api/users/me` |
| `changePassword(current, new, confirm)` | PATCH | `/api/users/me/password` |
| `uploadAvatar(file)` | POST | `/api/users/me/avatar` |
| `deleteAccount(password)` | DELETE | `/api/users/me` |

### `chatApi`

| Function | Method | Path |
|---|---|---|
| `listThreads(page, limit)` | GET | `/api/chat-threads` |
| `createThread(title)` | POST | `/api/chat-threads` |
| `renameThread(threadId, title)` | PATCH | `/api/chat-threads/{id}` |
| `deleteThread(threadId)` | DELETE | `/api/chat-threads/{id}` |
| `listMessages(threadId, page, limit)` | GET | `/api/chat-threads/{id}/messages` |
| `createMessage(threadId, content)` | POST | `/api/chat-threads/{id}/messages` |
| `updateMessage(messageId, content)` | PATCH | `/api/chat-messages/{id}` |
| `regenerateMessage(messageId)` | POST | `/api/chat-messages/{id}/regenerate` |

### `documentApi`

| Function | Method | Path |
|---|---|---|
| `upload(file)` | POST | `/api/documents/upload` |
| `list(page, limit)` | GET | `/api/documents` |
| `getStatus(documentId)` | GET | `/api/documents/{id}/status` |
| `delete(documentId)` | DELETE | `/api/documents/{id}` |

## TypeScript Types

All shared types are in `src/lib/types.ts`:

- `User` — id, name, email, profile_picture_url, created_at
- `ChatThread` — id, title, created_at, updated_at
- `ChatMessage` — id, thread_id, role, content, sources, created_at, edited_at
- `MessagePairResponse` — user_message + assistant_message (returned by `createMessage`)
- `EditMessageResponse` — updated user_message + new assistant_message
- `RegenerateResponse` — new assistant_message
- `DocumentListItem` — id, filename, content_type, status, processing_error, chunk_count, uploaded_at
- `DocumentStatusResponse` — id, status, processing_error, chunk_count
- `DocumentUploadResponse` — document_id, filename, status
- `PaginatedResponse<T>` — items, total, page, limit, pages
- `ApiError` — detail (string or array of `{msg, loc}`)

## Running Locally

```bash
cd frontend
npm install

# Ensure .env has NEXT_PUBLIC_API_URL=http://localhost:8000
# (so the browser can reach the backend directly during local dev)

npm run dev
# → http://localhost:3000
```

The middleware redirects unauthenticated users to `/login` automatically.

## Environment Variables

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL visible from the browser. Empty string in Docker (nginx proxies `/api/*`). `http://localhost:8000` for local dev without Docker. |

`NEXT_PUBLIC_*` variables are inlined at build time by Next.js webpack. The value in `.env` at build time is what gets embedded in the client bundle — changing it at runtime has no effect on the standalone production server.

## Production Build

The Docker image uses `output: 'standalone'` in `next.config.mjs`. The build process:

1. `npm ci` — clean install from `package-lock.json`
2. `npm run build` — Next.js build with `NEXT_PUBLIC_API_URL=""` (set in the Dockerfile)
3. The `.next/standalone/` output contains a self-contained `server.js` with all required Node.js modules
4. `.next/static/` and `public/` are copied into the runtime image alongside the standalone output

The runtime image runs `node server.js` on port 3000, which nginx proxies from port 80.
