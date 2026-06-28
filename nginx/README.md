# nginx

nginx:alpine reverse proxy that sits in front of both application services.

## What nginx does

- Exposes **port 80** to the host — the only port that needs to be open for the application to work.
- Routes `/api/*` and `/health` to the FastAPI backend container (`backend:8000`).
- Routes `/_next/static/*` to the frontend and serves those assets from a disk-backed proxy cache with a 365-day TTL.
- Routes everything else (`/`) to the Next.js frontend container (`frontend:3000`).
- Disables buffering and caching for the SSE streaming endpoint so tokens reach the browser immediately.
- Applies security headers to all responses.
- Both the backend and frontend are on Docker's internal network and are not reachable from outside the host.

## Routing Rules

| Path | Target | Caching |
|---|---|---|
| `~* /api/chat-threads/.*/messages/stream` | `http://backend:8000` | No cache, no buffering (SSE) |
| `/api/*` | `http://backend:8000` | No cache (`proxy_cache off`, `proxy_no_cache 1`) |
| `/health` | `http://backend:8000` | No cache |
| `/docs`, `/redoc`, `/openapi.json` | `http://backend:8000` | No cache |
| `/_next/static/` | `http://frontend:3000` | `static_cache` zone, 365-day TTL, `immutable` |
| `/` (everything else) | `http://frontend:3000` | No explicit cache |

The SSE location uses a regex (`~*`) so it is matched before the plain `/api/` prefix block.

## Proxy Cache

```nginx
proxy_cache_path /var/cache/nginx levels=1:2
    keys_zone=static_cache:10m max_size=500m
    inactive=60m use_temp_path=off;
```

The `/_next/static/` location uses this cache zone. Next.js content-hashes all filenames in this directory, so cached assets are safe to serve indefinitely — the file name changes when content changes.

```nginx
location /_next/static/ {
    proxy_cache        static_cache;
    proxy_cache_valid  200 365d;
    proxy_cache_use_stale error timeout updating;
    add_header Cache-Control  "public, max-age=31536000, immutable";
    add_header X-Cache-Status $upstream_cache_status;
}
```

`X-Cache-Status` is added to static asset responses so you can verify cache hits:
```bash
curl -I http://localhost/_next/static/chunks/main.js | grep X-Cache-Status
# X-Cache-Status: HIT   (after the first request)
```

API and SSE endpoints explicitly disable the cache:
```nginx
proxy_cache    off;
proxy_no_cache 1;
add_header Cache-Control "no-store";
```

## Configuration Notes

**`client_max_body_size 25M`** — Allows document uploads up to 25 MB. This must be at least as large as the upload limit enforced in the backend (`document_service.py`). Increase both if the limit is raised.

**Proxy timeouts** — LLM and RAG responses can take 30–60 seconds. The generic `/api/` block uses 120-second timeouts. The SSE streaming block uses 300-second timeouts to handle long-running data analysis queries:

```
# /api/ block
proxy_read_timeout    120s;
proxy_connect_timeout  10s;
proxy_send_timeout    120s;

# SSE block
proxy_read_timeout    300s;
proxy_connect_timeout  10s;
proxy_send_timeout    300s;
```

**SSE streaming** — The streaming endpoint requires these settings to prevent nginx from buffering tokens:

```nginx
proxy_buffering    off;
proxy_cache        off;
proxy_no_cache     1;
chunked_transfer_encoding on;
add_header Cache-Control    "no-store";
add_header X-Accel-Buffering "no";
```

**Gzip compression** is enabled for `text/plain`, `text/css`, `application/json`, `application/javascript`, and `image/svg+xml`. Binary files (images, PDFs) are not compressed.

**Security headers** applied to all responses through the server block:

```nginx
add_header X-Content-Type-Options  "nosniff"                         always;
add_header X-Frame-Options         "DENY"                            always;
add_header X-XSS-Protection        "1; mode=block"                   always;
add_header Referrer-Policy         "strict-origin-when-cross-origin" always;
proxy_hide_header X-Powered-By;
server_tokens off;
```

**Proxy headers forwarded to the backend:**

```
X-Real-IP         — original client IP
X-Forwarded-For   — full IP chain
X-Forwarded-Proto — original scheme (http or https)
Host              — original Host header
```

**`Upgrade` and `Connection` headers** are forwarded to the frontend for WebSocket support (used by Next.js HMR in development; harmless in production).

## SSL for Production

The current configuration serves HTTP only. To add HTTPS with Certbot on a Linux server:

1. Install Certbot on the host: `apt install certbot`
2. Obtain certificates: `certbot certonly --standalone -d yourdomain.com`
3. Update `nginx.conf` to listen on port 443 and add SSL certificate paths
4. Expose port 443 in `docker-compose.yml`: `- "443:443"`
5. Mount the certificate directory into the nginx container:
   ```yaml
   volumes:
     - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
     - /etc/letsencrypt:/etc/letsencrypt:ro
   ```
6. Optionally redirect HTTP → HTTPS with a separate `server {}` block listening on port 80

No rebuild is required — `nginx.conf` is mounted as a volume and nginx can reload it with `docker compose exec nginx nginx -s reload`.

## Updating the Configuration

`nginx.conf` is bind-mounted at runtime (`./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`), so changes take effect without rebuilding the image:

```bash
# Edit nginx/nginx.conf
docker compose exec nginx nginx -s reload
```

If the configuration has a syntax error, `nginx -s reload` will fail and the previous config stays active — the service never goes down.
