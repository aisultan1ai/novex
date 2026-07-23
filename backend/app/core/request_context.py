"""Per-request/task context: propagates `request_id` across the whole call
tree via a contextvar. Works transparently across FastAPI request handlers,
background threads (starlette threadpool), and Redis-stream workers.

Rules:
  * `get_request_id()` returns the current id or None if we're outside any
    bound scope.
  * Web requests: `RequestIdMiddleware` binds an id at the top of the ASGI
    stack — every log line and downstream HTTP call inside the request
    inherits it.
  * Workers: `dispatch_consumer` and the polling scheduler bind an id per
    job/tick using `bind_request_id(rid)` so the whole job's logs share
    the same trace id.
  * Producers (payment/orders services) call `streams.publish()`, which
    automatically stamps the current id into the message payload.
  * `CarrierGatewayClient` forwards the id as `X-Request-Id` on every
    outbound call to the gateway.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def set_request_id(request_id: str | None):
    """Set the current request id and return the token needed to reset it.

    Use `bind_request_id` for scoped binding — this raw setter is only for
    ASGI middleware where the scope is bounded by the async task lifetime.
    """
    return _request_id_ctx.set(request_id)


def reset_request_id(token) -> None:
    _request_id_ctx.reset(token)


@contextmanager
def bind_request_id(request_id: str | None = None) -> Iterator[str]:
    """Bind `request_id` for the duration of the `with` block.

    Passing None generates a fresh UUID4 hex — use this at the top of
    worker jobs / background ticks that have no upstream id.
    """
    rid = request_id or uuid.uuid4().hex
    token = _request_id_ctx.set(rid)
    try:
        yield rid
    finally:
        _request_id_ctx.reset(token)
