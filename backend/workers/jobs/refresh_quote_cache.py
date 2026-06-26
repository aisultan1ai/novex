from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.modules.quotes.models import QuoteSession

logger = logging.getLogger(__name__)

_STALE_SESSION_HOURS = 48
_HEARTBEAT_KEY = "worker:heartbeat"
_HEARTBEAT_TTL = 3600 * 2  # 2 hours — enough buffer beyond a 1800s interval
_LOCK_KEY = "lock:refresh_quote_cache"
_LOCK_TTL = 120  # seconds — must be < job interval (1800s)


def run(db: Session) -> None:
    r = get_redis()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
        logger.debug("refresh_quote_cache: skipped — another replica holds the lock")
        return
    try:
        _delete_stale_sessions(db)
        db.commit()
        _set_redis_heartbeat()
    finally:
        r.delete(_LOCK_KEY)


def _delete_stale_sessions(db: Session) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=_STALE_SESSION_HOURS)
    result = db.execute(
        delete(QuoteSession).where(
            QuoteSession.expires_at.is_(None),
            QuoteSession.created_at < cutoff,
        )
    )
    deleted = result.rowcount  # type: ignore[attr-defined]
    if deleted:
        logger.info("refresh_quote_cache: removed %d stale quote sessions (no expires_at)", deleted)


def _set_redis_heartbeat() -> None:
    try:
        from app.core.redis import get_redis
        get_redis().setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, datetime.utcnow().isoformat())
        logger.debug("refresh_quote_cache: Redis heartbeat updated")
    except Exception as exc:
        logger.warning("refresh_quote_cache: Redis heartbeat failed: %s", exc)
