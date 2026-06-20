# ── builder: install deps into isolated venv ──────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
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

# WeasyPrint fonts needed for Exline PDF generation (get_invoice_pdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-dejavu \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Carrier API clients + polling adapters (no DB models, no migrations)
COPY backend/app/modules/carriers  ./app/modules/carriers
COPY backend/app/modules/__init__.py ./app/modules/__init__.py
COPY backend/app/__init__.py       ./app/__init__.py
COPY backend/app/core/config.py    ./app/core/config.py
COPY backend/app/core/__init__.py  ./app/core/__init__.py
COPY backend/carrier_gateway       ./carrier_gateway
COPY backend/pyproject.toml        .

EXPOSE 8100

CMD ["uvicorn", "carrier_gateway.gateway:app", \
     "--host", "0.0.0.0", "--port", "8100", "--workers", "2"]
