from __future__ import annotations

from fastapi import Request
from slowapi import Limiter

from app.core.config import get_settings


def _real_ip(request: Request) -> str:
    # nginx sets X-Real-IP to the client IP for all /api/* locations.
    # Fall back to X-Forwarded-For, then to the direct TCP connection address.
    ip = request.headers.get("X-Real-IP")
    if ip:
        return ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(key_func=_real_ip, storage_uri=settings.redis_url)


limiter = _get_limiter()
