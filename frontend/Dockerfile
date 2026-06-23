# Stage 1: build the Next.js app
FROM node:20-alpine AS builder

WORKDIR /app

# NEXT_PUBLIC_* vars are inlined at build time by webpack.
# Empty string makes API calls relative ("/api/...") so nginx can proxy them.
ENV NEXT_PUBLIC_API_URL=""
ENV NEXT_TELEMETRY_DISABLED=1

COPY package*.json ./
RUN npm ci

COPY . .

# Ensure public/ exists so the COPY in the runtime stage never fails
RUN mkdir -p public

RUN npm run build

# Stage 2: minimal runtime image
FROM node:20-alpine

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Standalone output bundles everything the server needs — no node_modules required
COPY --from=builder --chown=appuser:appgroup /app/.next/standalone ./
# Static assets are NOT included in standalone — copy separately
COPY --from=builder --chown=appuser:appgroup /app/.next/static ./.next/static
COPY --from=builder --chown=appuser:appgroup /app/public ./public

USER appuser

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

EXPOSE 3000

CMD ["node", "server.js"]
