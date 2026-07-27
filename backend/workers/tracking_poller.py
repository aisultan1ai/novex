"""
Entry point for the dedicated tracking-poller container.

Runs only the sync_tracking job. Kept separate from workers/main.py so the
poller can be scaled independently (replicas=2+) without duplicating email or
dispatch jobs. Redis distributed lock in sync_tracking.py prevents dual-processing.
"""
from __future__ import annotations

import logging
import signal
from threading import Event

import sentry_sdk

# Import all ORM models so SQLAlchemy metadata is fully populated
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
from app.core.config import get_settings
from app.core.redis import get_redis
from workers.jobs import sync_tracking
from workers.scheduler import WorkerScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("novex.tracking_poller")

settings = get_settings()
stop_event = Event()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        release=settings.app_version,
    )
    logger.info("Sentry initialised in tracking-poller (env=%s)", settings.environment)

_ALIVE_KEY = "tracking_poller:alive"
_ALIVE_TTL = 180  # > poll interval (120s)


def _handle_shutdown(signum: int, _frame) -> None:
    logger.info("Received signal %s. Stopping tracking-poller...", signum)
    stop_event.set()


def run() -> None:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    logger.info(
        "Starting tracking-poller in %s mode. Gateway=%s",
        settings.environment,
        settings.carrier_gateway_url,
    )

    scheduler = WorkerScheduler()
    scheduler.register(sync_tracking.run, interval_secs=120)
    tick_interval = int(settings.tracking_poller_tick_interval_seconds)
    logger.info(
        "Tracking poller ready. Poll interval=120s, wake-up tick=%ds.", tick_interval,
    )

    while not stop_event.is_set():
        scheduler.tick()
        try:
            get_redis().setex(_ALIVE_KEY, _ALIVE_TTL, "1")
        except Exception:
            logger.warning("Tracking poller heartbeat write failed")
        # Short wake-ups so SIGTERM interrupts the loop within `tick_interval`
        # seconds instead of the previous 30s. This keeps the shutdown well
        # inside K8s terminationGracePeriodSeconds (usually 30s).
        stop_event.wait(timeout=tick_interval)

    logger.info("Tracking poller stopped cleanly.")


if __name__ == "__main__":
    run()
