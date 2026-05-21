from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.modules.dispatch.service import DispatchWorker

logger = logging.getLogger(__name__)

_worker = DispatchWorker()


def run(db: Session) -> None:
    processed = _worker.run_once(db)
    logger.info("dispatch_orders worker: processed %d jobs", processed)
