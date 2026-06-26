from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.modules.dispatch.service import DispatchWorker

logger = logging.getLogger(__name__)

_worker = DispatchWorker()

_LOCK_KEY = "lock:dispatch_orders"
_LOCK_TTL = 45  # seconds — must be < job interval (60s)


def run(db: Session) -> None:
    r = get_redis()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
        logger.debug("dispatch_orders: skipped — another replica holds the lock")
        return
    try:
        processed = _worker.run_once(db)
        logger.info("dispatch_orders worker: processed %d jobs", processed)
    finally:
        r.delete(_LOCK_KEY)
