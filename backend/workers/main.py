from __future__ import annotations

import logging
import signal
import threading
from threading import Event

import sentry_sdk

from app.core.config import get_settings
from app.core.db import check_database_connection
from app.core.redis import get_redis
from app.core.streams import ensure_consumer_groups

_ALIVE_KEY = "worker:alive"
_ALIVE_TTL = 90  # seconds — must be > main loop interval (30s)

# Import all ORM models so SQLAlchemy metadata is fully populated before any
# queries run. Without this, FK constraints (e.g. carrier_webhooks→carriers)
# raise NoReferencedTableError at flush time.
import app.modules.address_book.models  # noqa: F401
import app.modules.audit.models  # noqa: F401
import app.modules.carriers.api_credentials  # noqa: F401
import app.modules.carriers.integration_log  # noqa: F401
import app.modules.carriers.models  # noqa: F401
import app.modules.carriers.webhook_config  # noqa: F401
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
from workers.consumers import dispatch_consumer, email_consumer
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

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        release=settings.app_version,
    )
    logger.info("Sentry initialised in worker (env=%s)", settings.environment)


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

    ensure_consumer_groups()

    consumer_targets = (email_consumer.run, dispatch_consumer.run)
    consumer_threads: list[list] = []  # [[thread, target], ...]
    for target in consumer_targets:
        t = threading.Thread(target=target, args=(stop_event,), daemon=True, name=target.__module__)
        t.start()
        consumer_threads.append([t, target])
        logger.info("Started consumer thread: %s", t.name)

    scheduler = WorkerScheduler()
    scheduler.register(dispatch_orders.run, 60)
    scheduler.register(send_email_notifications.run, 60)
    scheduler.register(cleanup_expired_files.run, 3600)
    scheduler.register(retry_failed_callbacks.run, 300)
    scheduler.register(refresh_quote_cache.run, 1800)
    # sync_tracking also has a dedicated tracking-poller container in prod. Running
    # it here as well is safe: sync_tracking.run() acquires a Redis lock so only
    # one instance polls a given tick. In dev (no tracking-poller container) this
    # is the only place tracking gets polled.
    scheduler.register(sync_tracking.run, 120)
    logger.info("WorkerScheduler ready. Starting main loop.")

    while not stop_event.is_set():
        scheduler.tick()

        # Restart any consumer thread that exited unexpectedly.
        for entry in consumer_threads:
            t, target = entry
            if not t.is_alive() and not stop_event.is_set():
                logger.error(
                    "Consumer thread '%s' died unexpectedly; restarting.", t.name
                )
                new_t = threading.Thread(
                    target=target, args=(stop_event,), daemon=True, name=t.name
                )
                new_t.start()
                entry[0] = new_t

        try:
            get_redis().setex(_ALIVE_KEY, _ALIVE_TTL, "1")
        except Exception:
            logger.warning("Worker heartbeat write failed")
        stop_event.wait(timeout=30)

    logger.info("Worker stopped cleanly.")


if __name__ == "__main__":
    run()
