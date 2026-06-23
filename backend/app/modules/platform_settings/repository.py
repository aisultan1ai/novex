from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.platform_settings.models import PlatformSetting

_CACHE_PREFIX = "pset:"
_CACHE_TTL = 300  # 5 minutes — settings change rarely


def _cache_get(key: str) -> str | None:
    try:
        from app.core.redis import get_redis
        return get_redis().get(f"{_CACHE_PREFIX}{key}")  # type: ignore[return-value]
    except Exception:
        return None


def _cache_set(key: str, value: str) -> None:
    try:
        from app.core.redis import get_redis
        get_redis().setex(f"{_CACHE_PREFIX}{key}", _CACHE_TTL, value)
    except Exception:
        pass


def _cache_delete(key: str) -> None:
    try:
        from app.core.redis import get_redis
        get_redis().delete(f"{_CACHE_PREFIX}{key}")
    except Exception:
        pass


class PlatformSettingsRepository:
    def get(self, db: Session, key: str, default: str = "") -> str:
        cached = _cache_get(key)
        if cached is not None:
            return cached
        row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
        value = row.value if row else default
        _cache_set(key, value)
        return value

    def set(self, db: Session, key: str, value: str) -> PlatformSetting:
        row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
        if row:
            row.value = value
        else:
            row = PlatformSetting(key=key, value=value)
            db.add(row)
        db.flush()
        _cache_delete(key)
        return row
