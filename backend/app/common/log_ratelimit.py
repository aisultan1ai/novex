"""Per-process log rate limiter.

Hot paths (carrier polling, high-volume adapters) emit warnings for unknown
statuses on every event. Under mass tracking that floods the log stream with
duplicate lines. `log_once_per` collapses repeats of the same (logger, key)
tuple to at most one emission per `ttl` seconds.

Scope is per-process — a multi-worker deployment will still see one line per
worker per window. That is intentional: the goal is to keep logs readable,
not to guarantee a global singleton (which would need Redis or similar).
"""
from __future__ import annotations

import logging
import threading
import time

_lock = threading.Lock()
_last_emitted: dict[tuple[str, str], float] = {}

_DEFAULT_TTL = 3600.0  # 1 hour


def log_once_per(
    logger: logging.Logger,
    key: str,
    message: str,
    *args,
    level: int = logging.WARNING,
    ttl: float = _DEFAULT_TTL,
) -> None:
    """Emit `message % args` at most once per `ttl` seconds for the given key.

    `key` should be stable across occurrences that mean the same thing
    (e.g. carrier code + unknown status). Different keys log independently.
    """
    now = time.monotonic()
    cache_key = (logger.name, key)
    with _lock:
        last = _last_emitted.get(cache_key)
        if last is not None and (now - last) < ttl:
            return
        _last_emitted[cache_key] = now
    logger.log(level, message, *args)
