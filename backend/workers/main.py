from __future__ import annotations

import logging
import signal
from threading import Event

from app.core.config import get_settings
from app.core.db import check_database_connection

# Import all ORM models so SQLAlchemy metadata is fully populated before any
# queries run. Without this, FK constraints (e.g. carrier_webhooks→carriers)
# raise NoReferencedTableError at flush time.
import app.modules.address_book.models  # noqa: F401
import app.modules.audit.models  # noqa: F401
import app.modules.carriers.models  # noqa: F401
import app.modules.carriers.webhook_config  # noqa: F401
import app.modules.carriers.api_credentials  # noqa: F401
import app.modules.carriers.integration_log  # noqa: F401
import app.modules.commissions.models  # noqa: F401
import app.modules.dispatch.models  # noqa: F401
import app.modules.documents.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
import app.modules.notifications.models  # noqa: F401
import app.modules.orders.models  # noqa: F401
import app.modules.payments.models  # noqa: F401
import app.modules.platform_settings.models  # noqa: F401
import app.modules.quotes.models  # noqa: F401
import app.modules.reviews.models  # noqa: F401
import app.modules.shipments.models  # noqa: F401
import app.modules.tracking.models  # noqa: F401

from workers.jobs import (
    cleanup_expired_files,
    dispatch_orders,
    refresh_quote_cache,
    retry_failed_callbacks,
    send_email_notifications,
    sync_tracking,
)
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
    scheduler.register(send_email_notifications.run, 60)
    scheduler.register(cleanup_expired_files.run, 3600)
    scheduler.register(retry_failed_callbacks.run, 300)
    scheduler.register(refresh_quote_cache.run, 1800)
    logger.info("WorkerScheduler ready. Starting main loop.")

    while not stop_event.is_set():
        scheduler.tick()
        stop_event.wait(timeout=30)

    logger.info("Worker stopped cleanly.")


if __name__ == "__main__":
    run()
