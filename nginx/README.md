# nginx

nginx:alpine reverse proxy that sits in front of both application services.

## What nginx does

- Exposes **port 80** to the host — the only port that needs to be open for the application to work.
- Routes `/api/*` and `/health` to the FastAPI backend container (`backend:8000`).
- Routes everything else (`/`) to the Next.js frontend container (`frontend:3000`).
- Both the backend and frontend are on Docker's internal network and are not reachable from outside the host.

## Routing Rules

| Path | Target | Notes |
|---|---|---|
| `/api/*` | `http://backend:8000` | Full path forwarded as-is (e.g. `/api/auth/login`) |
| `/health` | `http://backend:8000` | Backend liveness probe also accessible from outside |
| `/` (everything else) | `http://frontend:3000` | Next.js handles all other routes |

## Configuration Notes

**`client_max_body_size 25M`** — Allows document uploads up to 25 MB. This must be at least as large as the upload limit enforced in the backend (`document_service.py`). Increase both if the limit is raised.

**Proxy timeouts set to 120 seconds** — LLM and RAG responses can take 30–60 seconds. The default nginx proxy timeout of 60 seconds is too short; 120 seconds provides headroom.

```
proxy_read_timeout    120s;
proxy_connect_timeout  10s;
proxy_send_timeout    120s;
```

**Gzip compression** is enabled for `text/plain`, `text/css`, `application/json`, `application/javascript`, and `image/svg+xml`. Binary files (images, PDFs) are not compressed.

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
