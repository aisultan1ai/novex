"""Shared cache for CarrierAPICredentials.

Reads carrier creds from Redis (5-min TTL by default), falls back to DB, and
persists the merged dict back to Redis. Consumers must call `invalidate_creds`
after any admin write so the next reader picks up the new values.

Historically the polling scheduler cached creds in-process while the tariff
engine live-quote calls read straight from env vars. That split meant an admin
password change in the UI took effect for dispatch/polling but was ignored by
/quote/results — with silent-failure symptoms and price drift.

Everything that talks to a carrier now goes through this module:
  * polling scheduler  → `get_creds(db, code)`
  * dispatch worker    → reads directly from DB, no cache needed (single lookup
                         per dispatch job)
  * tariff engine live → `get_creds(db, code)` sync, `get_creds_async(db,
                         code)` async
  * admin_carrier_api  → calls `invalidate_creds(code)` on upsert/update/delete
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.carriers.api_credentials import (
    CarrierAPICredentials,
    CarrierAPICredentialsRepository,
)

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "carrier_creds:"
_repo = CarrierAPICredentialsRepository()


def _cache_key(carrier_code: str) -> str:
    return f"{_CACHE_PREFIX}{carrier_code}"


def _dict_from_row(row: CarrierAPICredentials | None) -> dict:
    """Serialise a DB row into the plain dict the API clients consume.

    Inactive rows resolve to `{}` — callers can distinguish "no creds
    configured" from "creds present" via `bool(result)`.
    """
    if row is None or not row.is_active:
        return {}
    return {
        "api_url": row.api_url or "",
        "api_token": row.api_token or "",
        **(row.extra_config or {}),
    }


def _read_cache(carrier_code: str) -> dict | None:
    """Return the cached dict, or None on cache miss / Redis unavailable."""
    try:
        from app.core.redis import get_redis
        raw = get_redis().get(_cache_key(carrier_code))
        if raw:
            return json.loads(raw)  # type: ignore[arg-type]
    except Exception as exc:
        logger.debug("creds cache read failed for %s: %s", carrier_code, exc)
    return None


def _write_cache(carrier_code: str, value: dict) -> None:
    settings = get_settings()
    try:
        from app.core.redis import get_redis
        get_redis().setex(
            _cache_key(carrier_code),
            settings.polling_creds_ttl_seconds,
            json.dumps(value),
        )
    except Exception as exc:
        logger.debug("creds cache write failed for %s: %s", carrier_code, exc)


def invalidate_creds(carrier_code: str) -> None:
    """Drop the cached dict for a carrier.

    Call after any admin write (upsert / update / delete) so the next reader
    hits the DB and re-populates the cache with the new values.
    """
    try:
        from app.core.redis import get_redis
        get_redis().delete(_cache_key(carrier_code))
    except Exception as exc:
        logger.debug("creds cache invalidate failed for %s: %s", carrier_code, exc)


def get_creds(db: Session, carrier_code: str) -> dict:
    """Sync path — used by polling scheduler + tariff_engine sync flow."""
    cached = _read_cache(carrier_code)
    if cached is not None:
        return cached
    row = _repo.get_by_carrier_code(db, carrier_code)
    creds = _dict_from_row(row)
    _write_cache(carrier_code, creds)
    return creds


async def get_creds_async(db: AsyncSession, carrier_code: str) -> dict:
    """Async path — used by /shipping/quote → tariff_engine live calls."""
    cached = _read_cache(carrier_code)
    if cached is not None:
        return cached
    result = await db.execute(
        select(CarrierAPICredentials).where(
            CarrierAPICredentials.carrier_code == carrier_code
        )
    )
    row = result.scalar_one_or_none()
    creds = _dict_from_row(row)
    _write_cache(carrier_code, creds)
    return creds


def resolve_with_env_fallback(
    db_creds: dict[str, Any],
    env_map: dict[str, str],
    api_url_default: str = "",
) -> dict[str, Any]:
    """Merge DB-sourced creds with env-var fallbacks.

    `db_creds` takes precedence field-by-field. `env_map` maps the target
    dict key (e.g. `"login"`) to the env var name (e.g. `"EXLINE_LOGIN"`).
    Returned dict always contains an `api_url` (may be empty).
    """
    import os

    merged: dict[str, Any] = {}
    for key, env_name in env_map.items():
        merged[key] = str(db_creds.get(key) or os.getenv(env_name) or "")
    merged["api_url"] = str(
        db_creds.get("api_url") or os.getenv(env_map.get("api_url", "")) or api_url_default
    )
    return merged
