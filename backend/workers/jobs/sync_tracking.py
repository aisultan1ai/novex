from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.modules.carriers.polling.scheduler import poll_all_active_shipments

logger = logging.getLogger(__name__)

_LOCK_KEY = "lock:sync_tracking"
_LOCK_TTL = 90  # seconds — must exceed the longest expected poll run


def run(db: Session) -> None:
    r = get_redis()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
        logger.debug("sync_tracking: skipped — another replica holds the lock")
        return
    try:
        poll_all_active_shipments(db)
    finally:
        r.delete(_LOCK_KEY)
