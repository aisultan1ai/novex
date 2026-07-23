from __future__ import annotations

import logging
import sys

from app.core.request_context import get_request_id


class _RequestIdFilter(logging.Filter):
    """Attach the current request_id (from contextvar) to every LogRecord.

    Falls back to '-' when no id is bound (e.g. process bootstrap) so the
    formatter's %(request_id)s never blows up.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)-8s] [rid=%(request_id)s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler],
        force=True,
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
