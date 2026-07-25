from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis import get_redis
from app.modules.carriers.polling.scheduler import poll_all_active_shipments

logger = logging.getLogger(__name__)

_LOCK_KEY = "lock:sync_tracking"


def _lock_ttl() -> int:
    """TTL for the sync_tracking distributed lock.

    Read from settings so ops can raise it without a code change when a
    slow batch overruns the default. Previously hard-coded at 90 s, which
    was tight for a 200-item batch × 15 s HTTP timeout ÷ 10 workers (~300 s
    worst case). Now defaults to 300 s and is overridable via
    POLLING_LOCK_TTL_SECONDS.
    """
    return int(get_settings().polling_lock_ttl_seconds)


def run(db: Session) -> None:
    r = get_redis()
    ttl = _lock_ttl()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=ttl):
        logger.debug("sync_tracking: skipped — another replica holds the lock")
        return
    try:
        poll_all_active_shipments(db)
    finally:
        r.delete(_LOCK_KEY)
