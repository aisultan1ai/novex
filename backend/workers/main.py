from __future__ import annotations

import logging
import signal
from threading import Event

from app.core.config import get_settings
from app.core.db import check_database_connection
from workers.jobs import dispatch_orders, sync_tracking
from workers.scheduler import WorkerScheduler

settings = get_settings()
stop_event = Event()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("novex.worker")


def _handle_shutdown(signum: int, _frame) -> None:
    logger.info("Received signal %s. Stopping worker...", signum)
    stop_event.set()


def run() -> None:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    logger.info(
        "Starting Novex worker in %s mode. Redis=%s",
        settings.environment,
        settings.redis_url,
    )

    try:
        db_status = check_database_connection()
        logger.info("Database probe: %s", db_status)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database probe failed: %s", exc)

    scheduler = WorkerScheduler()
    scheduler.register(dispatch_orders.run, 60)
    scheduler.register(sync_tracking.run, 120)
    logger.info("WorkerScheduler ready. Starting main loop.")

    while not stop_event.is_set():
        scheduler.tick()
        stop_event.wait(timeout=30)

    logger.info("Worker stopped cleanly.")


if __name__ == "__main__":
    run()
