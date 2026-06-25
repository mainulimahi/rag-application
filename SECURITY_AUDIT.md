# Security Audit Report

**Date:** 2026-06-25
**Branch:** v2-data-analysis
**Auditor:** Claude Code automated audit (Parts 2, 3, 4)

---

## Executive Summary

The RAG application received a comprehensive four-part security audit covering input validation, injection prevention, file upload security, sensitive data exposure, rate limiting, CORS configuration, security headers, dependency vulnerabilities, encryption hygiene, and infrastructure hardening. All Critical and High findings have been resolved. The application is production-ready from a security standpoint after the recommended pre-deployment checklist is followed.

---

## Findings

### Critical

No Critical findings.

---

### High

| # | Category | File | Issue | Status |
|---|---|---|---|---|
| H1 | Dependency CVE | `backend/requirements.txt`, `backend/app/services/auth_service.py` | `python-jose` (CVE-2022-29217, CVSS 7.5): algorithm-confusion attack; library unmaintained since 3.3.0 (2021) | **Fixed** — migrated to `PyJWT>=2.8.0` |
| H2 | Dependency CVE | `frontend/package.json` | Next.js 14.x: HTTP request deserialization DoS (GHSA-h25m-26qc-wcjf, CVSS 7.5) in RSC when using insecure patterns | **Fixed** — upgraded to `next@^15.0.0` |
| H3 | Injection | `backend/app/services/duckdb_service.py` | `_write_temp_file()` used `os.path.basename()` which is bypassable on Windows; no path-start assertion | **Fixed (Part 2)** — `Path().name` + `..` assertion + `TEMP_DIR` prefix check |
| H4 | Injection | `backend/app/agents/data_agent_node.py` | SQL validator missing `UNION`, `EXEC`, `EXECUTE`, `TRUNCATE`, `COPY`; no multi-statement detection | **Fixed (Part 2)** — extended forbidden keyword lists; added `;\s*(select|...)` multi-statement check |
| H5 | XSS | `frontend/src/components/chat/ChatMessages.tsx` | AI-generated markdown rendered without sanitization — arbitrary HTML/script injection via crafted LLM output | **Fixed (Part 2)** — `rehype-sanitize` applied to both ReactMarkdown instances |
| H6 | Rate limiting | `backend/app/api/chat.py` | Chat message endpoints had no rate limit — unlimited LLM API calls per user | **Fixed (Part 3)** — `@limiter.limit("60/minute", key_func=get_user_id_key)` on both message endpoints |
| H7 | CORS | `backend/app/main.py` | `allow_methods=["*"]`, `allow_headers=["*"]`, and hardcoded origin `http://localhost:3000` | **Fixed (Part 3)** — explicit methods/headers; origins from `settings.ALLOWED_ORIGINS` |

---

### Medium

| # | Category | File | Issue | Status |
|---|---|---|---|---|
| M1 | Injection | `backend/app/schemas/data_source.py` | `SQLiteConfig.file_path` accepted `..` traversal and relative paths — could access files outside allowed locations | **Fixed (Part 2)** — Pydantic `field_validator` blocks `..` and requires absolute path |
| M2 | File upload | `backend/app/services/document_service.py` | No zip-bomb check on `.docx`/`.xlsx` — a 45 KB zip with 1 GB uncompressed content would exhaust memory | **Fixed (Part 2)** — 100 MB uncompressed limit via `zipfile.ZipFile` inspection |
| M3 | File upload | `backend/app/services/data_file_service.py` | No magic-bytes validation for Parquet/Excel; no zip-bomb check for Excel; no JSON parse pre-check | **Fixed (Part 2)** — `validate_data_file_content()` added; Parquet magic bytes, Excel MIME + zip-bomb, JSON parse check |
| M4 | File upload | `backend/app/services/document_service.py`, `data_file_service.py` | Upload filenames stored in DB without sanitization — path traversal via crafted `Content-Disposition` header | **Fixed (Part 2)** — `sanitize_filename()` applied before DB insert in both services |
| M5 | Rate limiting | `backend/app/api/auth.py` | `POST /api/auth/verify-email` had no rate limit — verification tokens could be brute-forced | **Fixed (Part 3)** — `@limiter.limit("10/minute")` added |
| M6 | Rate limiting | `backend/app/api/users.py` | Avatar upload and stats endpoint had no rate limits | **Fixed (Part 3)** — 10/min (avatar) and 30/min (stats) with user-id key |
| M7 | Rate limiting | `backend/app/core/limiter.py` | Authenticated rate-limited endpoints used IP key — users behind shared NAT shared a bucket | **Fixed (Part 3)** — `get_user_id_key()` extracts user_id from JWT cookie for authenticated endpoints |
| M8 | Secrets hygiene | `backend/app/core/config.py` | No validation of `FERNET_SECRET_KEY` format — a misconfigured key would cause a cryptic runtime error on first encrypt/decrypt, not a startup error | **Fixed** — `field_validator` checks URL-safe base64 decode and 32-byte length |
| M9 | Secrets hygiene | `backend/app/core/config.py` | No validation of `JWT_SECRET_KEY` strength — a short key weakens HS256 | **Fixed** — `field_validator` enforces minimum 32-character length |
| M10 | Version control | `.gitignore`, `frontend/.env` | `frontend/.env` was committed in commit `7d57c0e` (content: `NEXT_PUBLIC_API_URL=http://localhost:8000`, non-secret); `.gitignore` used `/.env` which only matches the root file | **Fixed** — added `frontend/.env` to `.gitignore`; ran `git rm --cached frontend/.env` |
| M11 | DoS | `docker-compose.yml` | No memory limits on any container — a runaway DuckDB query or memory leak could exhaust host memory and bring down all services | **Fixed** — `deploy.resources.limits.memory` set: backend 1G, postgres 512M, frontend 256M, nginx 128M |
| M12 | Dependency CVE | `frontend/package.json` | Next.js 14.x additional DoS CVEs (GHSA-9g9p-9gw9-jx7f image optimizer, GHSA-ggv3-7p47-pfv8 request smuggling in rewrites, GHSA-3x4c-7xq6-9pq8 disk cache) | **Fixed** — upgraded to `next@^15.0.0` which addresses all four next.js CVEs |

---

### Low

| # | Category | File | Issue | Status |
|---|---|---|---|---|
| L1 | Security headers | `backend/app/main.py` | Missing `Permissions-Policy` header | **Fixed (Part 3)** — `camera=(), microphone=(self), geolocation=()` |
| L2 | Security headers | `backend/app/main.py` | No Content-Security-Policy header | **Fixed (Part 3)** — CSP injected for `ENVIRONMENT=production` |
| L3 | Security headers | `nginx/nginx.conf` | nginx missing `server_tokens off` and security headers at proxy layer | **Fixed (Part 3)** — `server_tokens off`, X-Frame, X-Content-Type, X-XSS-Protection, Referrer-Policy, proxy_hide_header X-Powered-By |
| L4 | Rate limiting | `backend/app/api/data_sources.py`, `data_files.py` | Existing rate limits used IP key instead of user-id key for authenticated endpoints | **Fixed (Part 3)** — switched to `get_user_id_key` |
| L5 | Rate limiting | `backend/app/main.py` | 429 responses had no `Retry-After` header; response body was not structured JSON with a `type` field | **Fixed (Part 3)** — `Retry-After: N` header added; body includes `type: "rate_limit_exceeded"` |
| L6 | Infrastructure | `docker-compose.yml` | Postgres port 5432 exposed to host with no warning comment | **Fixed** — added "PRODUCTION: remove this port mapping" comment |

---

### Informational (OK — no issue)

| # | Category | File | Finding |
|---|---|---|---|
| I1 | Dependency | `backend/requirements.txt` | `cryptography>=42.0.0` — correctly pinned; 42.x+ has all critical security fixes |
| I2 | Dependency | `backend/requirements.txt` | `bcrypt==4.0.1` — correctly pinned; passlib 1.7.4 is incompatible with bcrypt>=4.1 (`__about__` removed) |
| I3 | Dependency | `frontend/package.json` | `react-markdown@^10.1.0` — latest stable; no known XSS issues at this version |
| I4 | Dependency | `frontend/package.json` | `rehype-sanitize@^6.0.0` — present and applied to both ReactMarkdown instances (added in Part 2) |
| I5 | Auth | `backend/app/services/auth_service.py` | Refresh tokens stored as SHA-256 hashes in DB; rotated on every use |
| I6 | Auth | `backend/app/api/auth.py` | Login rate-limited 5/min; signup 3/min; forgot-password 3/min; reset-password 3/min; resend-verification 2/hour |
| I7 | Auth | `backend/app/api/auth.py` | JWT cookies are `httpOnly=True`, `samesite="lax"`, `secure=True` in production |
| I8 | Containers | `backend/Dockerfile`, `frontend/Dockerfile` | Both images run as `appuser` (non-root); files owned by `appuser:appgroup` |
| I9 | Containers | `docker-compose.yml` | All sensitive values use `${VARIABLE}` env var substitution; no literal secrets in compose file |
| I10 | Containers | `backend/Dockerfile`, `frontend/Dockerfile` | No `ENV` instructions with real secret values; secrets injected at runtime via `env_file` |
| I11 | Secrets | `backend/app/`, `frontend/src/` | Grep for hardcoded API keys, passwords, and secrets returned zero matches |
| I12 | Git | `.env` | Root `.env` was never committed; confirmed via `git log --all --full-history -- .env` (no commits) |
| I13 | Multi-tenancy | All service files | Every query filters by `user_id`; pgvector search always scoped; `get_thread()` gates all thread operations |
| I14 | Data exposure | `backend/app/schemas/data_source.py`, `backend/app/api/data_sources.py` | Credentials never returned in API responses; `_assert_no_credentials()` runtime check in API layer |
| I15 | DuckDB | `backend/app/agents/data_agent_node.py` | Data agent re-verifies file and source ownership before executing any query |
| I16 | Health check | `backend/app/main.py` | `GET /health` returns 503 with `database: "unreachable"` when Postgres is down |
| I17 | Encryption | `backend/app/core/encryption.py` | Fernet symmetric encryption for data source credentials; single decryption site in `data_source_service.get_decrypted_config()` |

---

## Fixes Applied

### Part 2 — Input Validation & Injection Prevention, File Upload Security, Sensitive Data Exposure

| Fix | File(s) Changed |
|-----|----------------|
| DuckDB temp file path traversal — `Path().name`, `..` assertion, TEMP_DIR prefix check | `backend/app/services/duckdb_service.py` |
| SQL validator — added UNION, EXEC, EXECUTE, TRUNCATE, COPY, multi-statement detection | `backend/app/agents/data_agent_node.py` |
| SQLite path traversal — Pydantic validator blocks `..` and non-absolute paths | `backend/app/schemas/data_source.py` |
| XSS via markdown — `rehype-sanitize` added to both ReactMarkdown instances | `frontend/src/components/chat/ChatMessages.tsx`, `frontend/package.json` |
| Upload filename sanitization — `sanitize_filename()` before DB insert | `backend/app/services/document_service.py`, `backend/app/services/data_file_service.py` |
| Zip bomb protection — 100 MB uncompressed limit on `.docx` and `.xlsx` | `backend/app/services/document_service.py`, `backend/app/services/data_file_service.py` |
| Magic bytes validation — Parquet magic, Excel MIME, JSON pre-parse | `backend/app/services/data_file_service.py` |

### Part 3 — Rate Limiting, CORS, Security Headers

| Fix | File(s) Changed |
|-----|----------------|
| `get_user_id_key` — JWT-based rate limit key for authenticated endpoints (fallback to IP) | `backend/app/core/limiter.py` |
| Rate limit `POST /api/auth/verify-email` — 10/minute | `backend/app/api/auth.py` |
| Rate limit chat message endpoints — 60/minute per user | `backend/app/api/chat.py` |
| Rate limit avatar upload (10/min) and stats (30/min) | `backend/app/api/users.py` |
| Switch data-sources test + data-files upload to user-id key | `backend/app/api/data_sources.py`, `backend/app/api/data_files.py` |
| 429 handler — `Retry-After` header, structured `type: "rate_limit_exceeded"` body | `backend/app/main.py` |
| CORS — origins from `settings.ALLOWED_ORIGINS`; explicit methods and headers | `backend/app/main.py`, `backend/app/core/config.py` |
| Security headers — `Permissions-Policy`, production CSP | `backend/app/main.py` |
| nginx hardening — `server_tokens off`, security headers with `always`, `proxy_hide_header X-Powered-By` | `nginx/nginx.conf` |
| `.env.example` — added `ALLOWED_ORIGINS` documentation | `.env.example` |

### Part 4 — Dependency Updates, Encryption Validation, Infrastructure

| Fix | File(s) Changed |
|-----|----------------|
| Replace `python-jose` (CVE-2022-29217) with `PyJWT>=2.8.0` | `backend/requirements.txt`, `backend/app/services/auth_service.py` |
| Upgrade Next.js 14.x → 15.x; upgrade `eslint-config-next` 14.x → 15.x | `frontend/package.json`, `frontend/package-lock.json` |
| Fernet key validator — checks URL-safe base64 decode and 32-byte length on startup | `backend/app/core/config.py` |
| JWT secret validator — enforces minimum 32-character length on startup | `backend/app/core/config.py` |
| `frontend/.env` untracked from git; `.gitignore` updated to cover `frontend/.env` | `.gitignore` |
| Postgres port production warning comment | `docker-compose.yml` |
| Container memory limits — 1G backend, 512M postgres, 256M frontend, 128M nginx | `docker-compose.yml` |

---

## Remaining Known Limitations

| # | Issue | Reason Not Fixed | Recommended Action |
|---|-------|------------------|--------------------|
| R1 | `postcss` moderate CVE (PostCSS XSS via unescaped `</style>` in CSS stringify) — affects `next@15.x` transitive dep | Fix requires Next.js 16 (major version); postcss only runs at build time, not at runtime — exploitability requires attacker control of CSS input during build | Upgrade to Next.js 16 when stable; risk is Low in practice |
| R2 | `eslint-config-next` / `glob` high CVE (CLI command injection via `-c/--cmd`) | Fix (`eslint-config-next@16.x`) requires Next.js 16; glob CVE requires using `glob` as a CLI with specific flags — not triggered by library usage in ESLint | Upgrade to Next.js 16 / eslint-config-next 16 when stable; risk is negligible (dev-only, not web-accessible) |
| R3 | `frontend/.env` appears in git history (commit `7d57c0e`, "auth restored") | Git history rewrite (filter-branch / BFG) requires coordination and force-push to all forks; file only contains `NEXT_PUBLIC_API_URL=http://localhost:8000` (non-secret) | If any secret is ever accidentally committed, use BFG Repo Cleaner to purge it and rotate all affected credentials immediately |
| R4 | No automated dependency scanning in CI/CD | No CI pipeline exists yet | Set up GitHub Actions with `pip-audit` (backend) and `npm audit --audit-level=high` (frontend) as required checks on every PR |
| R5 | `passlib[bcrypt]` — passlib is in maintenance mode (last release 2023); `bcrypt==4.0.1` pin is required due to passlib incompatibility with newer bcrypt | No actively maintained drop-in replacement that works with the existing password hash format without a migration | Monitor `passlib` for critical CVEs; consider migrating to `bcrypt` directly (requires one-time password re-hash on next login) |
| R6 | CSP in production does not include a nonce/hash for inline scripts used by Next.js | Next.js standalone output injects inline scripts for hydration; `'unsafe-inline'` for scripts would be required without nonce support in nginx | When deploying to production, evaluate Next.js nonce-based CSP support (available in Next.js 13.4+) and set `script-src 'nonce-{nonce}'` via middleware |

---

## Recommended Next Steps Before Production Deployment

1. **Set `ENVIRONMENT=production`** in `.env` — enables `secure=True` on cookies and injects the CSP header
2. **Set `ALLOWED_ORIGINS=["https://yourdomain.com"]`** in `.env`
3. **Verify domain with Resend** and set `REQUIRE_EMAIL_VERIFICATION=true`
4. **Remove postgres port mapping** (`- "${POSTGRES_PORT:-5432}:5432"`) from `docker-compose.yml` — only the backend container needs DB access; exposing 5432 to the host increases attack surface
5. **Set up SSL termination** via Certbot + nginx (nginx handles TLS; add `listen 443 ssl` and redirect 80 → 443)
6. **Rotate all API keys** — generate fresh `JWT_SECRET_KEY`, `FERNET_SECRET_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`, `RESEND_API_KEY` for production; never reuse dev keys
7. **Set up automated dependency scanning** — `pip-audit` and `npm audit --audit-level=high` in CI/CD on every PR; fail the build on High/Critical
8. **Add `docker compose pull`** to deployment pipeline to keep base images (postgres, nginx, node, python) up to date
9. **Enable Postgres connection SSL** — add `?ssl=require` to `database_url` and configure pgvector to accept SSL-only connections
10. **Review nginx for production** — add `add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;` once HTTPS is configured
