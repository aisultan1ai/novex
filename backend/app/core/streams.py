from __future__ import annotations

import redis as redis_lib

from app.core.redis import get_redis

STREAM_EMAILS = "novex:emails"
STREAM_DISPATCH = "novex:dispatch"

GROUP_EMAILS = "email_workers"
GROUP_DISPATCH = "dispatch_workers"

_GROUPS: dict[str, str] = {
    STREAM_EMAILS: GROUP_EMAILS,
    STREAM_DISPATCH: GROUP_DISPATCH,
}


def publish(stream: str, data: dict[str, str]) -> None:
    get_redis().xadd(stream, data)


def ensure_consumer_groups() -> None:
    r = get_redis()
    for stream, group in _GROUPS.items():
        try:
            r.xgroup_create(stream, group, id="$", mkstream=True)
        except redis_lib.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
