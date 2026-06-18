from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _get_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


limiter = _get_limiter()
