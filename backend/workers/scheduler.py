from __future__ import annotations

import logging
import time
from typing import Callable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class WorkerScheduler:
    def __init__(self) -> None:
        self._jobs: list[tuple[Callable[[Session], None], int]] = []
        self._last_run: dict[str, float] = {}

    def register(self, fn: Callable[[Session], None], interval_secs: int) -> None:
        self._jobs.append((fn, interval_secs))
        self._last_run[fn.__name__] = 0.0
        logger.info("Registered job %s every %ds", fn.__name__, interval_secs)

    def tick(self) -> None:
        from app.core.db import SessionLocal

        now = time.monotonic()
        for fn, interval in self._jobs:
            key = fn.__name__
            if now - self._last_run.get(key, 0.0) < interval:
                continue
            with SessionLocal() as db:
                try:
                    fn(db)
                    self._last_run[key] = now
                except Exception:
                    logger.exception("Job %s failed, rolling back", key)
                    db.rollback()
