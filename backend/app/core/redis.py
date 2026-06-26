from __future__ import annotations

import logging

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None

_RETRY = Retry(ExponentialBackoff(cap=10, base=1), retries=5)
_RETRYABLE = [redis.exceptions.ConnectionError, redis.exceptions.TimeoutError]


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        url = get_settings().redis_url
        _client = redis.from_url(
            url,
            decode_responses=True,
            retry_on_timeout=True,
            retry_on_error=_RETRYABLE,
            retry=_RETRY,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
        logger.debug("Redis client initialised: %s", url)
    return _client


def reset_redis() -> None:
    """Force-close the singleton and allow re-creation (used in tests)."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
