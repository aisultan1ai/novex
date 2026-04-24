FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install \
    pydantic \
    pydantic-settings \
    sqlalchemy \
    psycopg2-binary \
    alembic \
    redis \
    httpx \
    python-dotenv \
    "PyJWT>=2.8" \
    "email-validator>=2.0"

EXPOSE 8001