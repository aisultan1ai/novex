# ── deps: cache node_modules as a separate layer ──────────────────────────────
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# ── builder: compile Next.js ──────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# NEXT_PUBLIC_* переменные вшиваются в клиентский бандл на build-time.
# Compose пробрасывает их через build.args → они доступны в этом стадии как ENV,
# и Next.js подхватывает их в момент `npm run build`.
ARG NEXT_PUBLIC_SUPPORT_EMAIL
ARG NEXT_PUBLIC_SUPPORT_PHONE
ARG NEXT_PUBLIC_PARTNERS_EMAIL
ARG NEXT_PUBLIC_OFFICE_ADDRESS

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    NEXT_PUBLIC_SUPPORT_EMAIL=${NEXT_PUBLIC_SUPPORT_EMAIL} \
    NEXT_PUBLIC_SUPPORT_PHONE=${NEXT_PUBLIC_SUPPORT_PHONE} \
    NEXT_PUBLIC_PARTNERS_EMAIL=${NEXT_PUBLIC_PARTNERS_EMAIL} \
    NEXT_PUBLIC_OFFICE_ADDRESS=${NEXT_PUBLIC_OFFICE_ADDRESS}

RUN npm run build

# ── runner: standalone server (~100 MB vs ~500 MB with full node_modules) ─────
FROM node:20-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

COPY --from=builder /app/public            ./public
COPY --from=builder /app/.next/standalone  ./
COPY --from=builder /app/.next/static      ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
