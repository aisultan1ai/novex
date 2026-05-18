# ── builder: same deps as backend minus HTTP-server packages ──────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/pyproject.toml .
RUN pip install --upgrade pip && pip install .

# ── runtime ────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

COPY backend/app          ./app
COPY backend/workers      ./workers
COPY backend/integrations ./integrations
COPY backend/migrations   ./migrations
COPY backend/alembic.ini  .
COPY backend/pyproject.toml .

EXPOSE 8001

# Update to actual worker entrypoint once workers module is implemented
CMD ["python", "-m", "workers.main"]
