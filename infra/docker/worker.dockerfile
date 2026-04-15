FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install \
    pydantic \
    pydantic-settings \
    python-dotenv \
    httpx \
    redis

CMD ["python", "-c", "import time; print('Novex worker container started'); time.sleep(10**9)"]