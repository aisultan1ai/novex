from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.modules.quotes.models import QuoteSession

logger = logging.getLogger(__name__)

_STALE_SESSION_HOURS = 48
_HEARTBEAT_KEY = "worker:heartbeat"
_HEARTBEAT_TTL = 3600 * 2  # 2 hours — enough buffer beyond a 1800s interval


def run(db: Session) -> None:
    _delete_stale_sessions(db)
    db.commit()
    _set_redis_heartbeat()


def _delete_stale_sessions(db: Session) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=_STALE_SESSION_HOURS)
    result = db.execute(
        delete(QuoteSession).where(
            QuoteSession.expires_at.is_(None),
            QuoteSession.created_at < cutoff,
        )
    )
    deleted = result.rowcount
    if deleted:
        logger.info("refresh_quote_cache: removed %d stale quote sessions (no expires_at)", deleted)


def _set_redis_heartbeat() -> None:
    try:
        from app.core.redis import get_redis
        get_redis().setex(_HEARTBEAT_KEY, _HEARTBEAT_TTL, datetime.utcnow().isoformat())
        logger.debug("refresh_quote_cache: Redis heartbeat updated")
    except Exception as exc:
        logger.warning("refresh_quote_cache: Redis heartbeat failed: %s", exc)
