from __future__ import annotations

import redis as redis_lib

from app.core.redis import get_redis
from app.core.request_context import get_request_id

STREAM_EMAILS = "novex:emails"
STREAM_DISPATCH = "novex:dispatch"

GROUP_EMAILS = "email_workers"
GROUP_DISPATCH = "dispatch_workers"

REQUEST_ID_FIELD = "request_id"

_GROUPS: dict[str, str] = {
    STREAM_EMAILS: GROUP_EMAILS,
    STREAM_DISPATCH: GROUP_DISPATCH,
}


def publish(stream: str, data: dict[str, str]) -> None:
    """Publish to a stream with the caller's trace id stamped in.

    Consumers should read `request_id` back and bind it via
    `request_context.bind_request_id` so the whole worker job shares
    the same trace id as the request that produced it.
    """
    payload = dict(data)
    if REQUEST_ID_FIELD not in payload:
        rid = get_request_id()
        if rid:
            payload[REQUEST_ID_FIELD] = rid
    get_redis().xadd(stream, payload)  # type: ignore[arg-type]


def ensure_consumer_groups() -> None:
    r = get_redis()
    for stream, group in _GROUPS.items():
        try:
            r.xgroup_create(stream, group, id="$", mkstream=True)
        except redis_lib.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
