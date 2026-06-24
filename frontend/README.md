# Frontend

Next.js 14 frontend for the RAG application. Built with the App Router, TypeScript strict mode, and no component libraries — all UI is custom CSS via `globals.css`.

## Architecture

```
src/
├── app/
│   ├── (app)/           Authenticated pages (chat, documents, profile)
│   ├── (auth)/          Unauthenticated pages (login, signup, etc.)
│   ├── globals.css      All styles — custom properties + component styles
│   ├── layout.tsx       Root layout (inline theme-init script, no flash on load)
│   └── page.tsx         Root route → redirects to /login
├── components/
│   ├── auth/            AuthCard shared form primitives
│   ├── chat/            ChatSidebar, ChatMessages, ChatInput
│   ├── documents/       DocumentsPanel
│   └── Toast.tsx        Module-level pub/sub toast notifications
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
| `/profile` | `app/(app)/profile/page.tsx` | Auth required | Name edit, avatar upload, password change, appearance (theme), usage stats, delete all chats, account deletion |

## Components

### `components/Toast.tsx`

Module-level pub/sub toast notification system. No React context required — any module can call `showToast(message, type)` and the `<Toaster>` component (mounted in the root layout) displays it. Supports `success`, `error`, and `info` types with auto-dismiss.

### `components/auth/AuthCard.tsx`

Shared primitives for all auth pages:
- `AuthCard` — centered card layout with title and subtitle
- `Field` — labelled input with consistent styling
- `SubmitButton` — primary submit button with loading state
- `Alert` — inline error or success message (`type="error" | "success"`)

### `components/chat/ChatSidebar.tsx`

Left sidebar listing all chat threads.

- **Collapse / expand**: toggle button collapses the sidebar to an icon strip; state persisted in `localStorage`
- **Resize**: drag handle on the right edge lets the user resize between 200–400 px; width persisted in `localStorage`
- **Pinned threads**: pinned threads appear in a separate section at the top with a visual indicator; pinned threads cannot be deleted until unpinned
- **Thread actions**: inline rename (click-to-edit, Enter/Escape to commit/cancel), pin/unpin, delete (with confirmation; delete button hidden on pinned threads)
- **Lazy new chat**: clicking "New Chat" shows a virtual pending item — no API call until the first message is sent
- **Load more**: paginated thread list with a "Load more" button
- **Footer**: link to Documents page; user avatar + name linking to Profile; logout button
- **Mobile**: overlay with backdrop on small screens

### `components/chat/ChatMessages.tsx`

Message list with:
- Markdown rendering (`react-markdown` v10 + `remark-gfm`) for assistant messages
- Code blocks with language label and copy button
- Streaming display: `status` events shown as animated pulse label; `token` events render characters progressively with a blinking cursor; typing dots shown before first token arrives
- Per-message actions: **Copy** (raw text to clipboard), **Regenerate** (re-run agent), **Edit** (user messages only — inline textarea)
- Source badges on assistant messages (`📄 From your documents`, `🌐 Web search`, `📄🌐 Documents + Web`; no badge for `llm_only`)
- Suggested prompts on empty state
- Scroll-to-bottom button when scrolled up
- Load older messages button (paginated history)
- Loading skeleton while fetching initial messages

### `components/chat/ChatInput.tsx`

Auto-growing textarea.
- Enter sends, Shift+Enter inserts a newline
- Disabled while a response is generating
- **Voice input**: microphone button uses the browser `SpeechRecognition` API to transcribe speech into the textarea; hidden on browsers that do not support it

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
| `stats()` | GET | `/api/users/me/stats` |

### `chatApi`

| Function | Method | Path |
|---|---|---|
| `listThreads(page, limit)` | GET | `/api/chat-threads` |
| `createThread(title?)` | POST | `/api/chat-threads` |
| `renameThread(threadId, title)` | PATCH | `/api/chat-threads/{id}` |
| `pinThread(threadId)` | PATCH | `/api/chat-threads/{id}/pin` |
| `deleteThread(threadId)` | DELETE | `/api/chat-threads/{id}` |
| `deleteAllChats(password)` | DELETE | `/api/chat-threads` |
| `listMessages(threadId, page, limit)` | GET | `/api/chat-threads/{id}/messages` |
| `createMessage(threadId, content)` | POST | `/api/chat-threads/{id}/messages` |
| `streamMessage(threadId, content)` | POST | `/api/chat-threads/{id}/messages/stream` |
| `updateMessage(messageId, content)` | PATCH | `/api/chat-messages/{id}` |
| `regenerateMessage(messageId)` | POST | `/api/chat-messages/{id}/regenerate` |

`streamMessage` is an async generator that yields `StreamEvent` objects parsed from the SSE response body.

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
- `ChatThread` — id, user_id, title, **pinned**, created_at, updated_at
- `ChatMessage` — id, thread_id, user_id, role, content, sources, created_at, edited_at
- `MessagePairResponse` — user_message + assistant_message + thread (returned by `createMessage`)
- `EditMessageResponse` — updated_message + assistant_message + deleted_message_ids
- `RegenerateResponse` — assistant_message
- `DocumentListItem` — id, filename, content_type, status, processing_error, chunk_count, uploaded_at
- `DocumentStatusResponse` — id, status, processing_error, chunk_count
- `DocumentUploadResponse` — id, filename, content_type, status, uploaded_at
- `UserStats` — documents_count, total_chunks, responses_generated, total_input_tokens, total_output_tokens, total_tokens
- `DeleteAllChatsResponse` — deleted_count
- `StreamEvent` — discriminated union: `{type:"status"|"token", content:string}` | `{type:"done", user_message, assistant_message, thread}` | `{type:"error", content:string}`
- `PaginatedResponse<T>` — items, total, page, limit, pages
- `ApiError` — detail (string or array of `{msg, type}`)

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

`NEXT_PUBLIC_*` variables are inlined at build time by Next.js. The value in `.env` at build time is what gets embedded in the client bundle — changing it at runtime has no effect on the standalone production server.

## Theming

Light and dark modes are implemented with CSS custom properties under a `data-theme` attribute on `<html>`.

- `layout.tsx` contains an inline `<script>` that reads `localStorage` (key `theme`) before React hydrates, falling back to `prefers-color-scheme`. This prevents any flash of the wrong theme on load.
- Users switch themes from **Profile → Appearance**, which shows Light and Dark clickable cards. Selecting one writes to `localStorage` and sets `document.documentElement.setAttribute('data-theme', ...)`.

## Production Build

The Docker image uses `output: 'standalone'` in `next.config.mjs`. The build process:

1. `npm ci` — clean install from `package-lock.json`
2. `npm run build` — Next.js build with `NEXT_PUBLIC_API_URL=""` (set in the Dockerfile)
3. The `.next/standalone/` output contains a self-contained `server.js` with all required Node.js modules
4. `.next/static/` and `public/` are copied into the runtime image alongside the standalone output

The runtime image runs `node server.js` on port 3000, which nginx proxies from port 80.
