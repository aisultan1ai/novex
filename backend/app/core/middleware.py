from __future__ import annotations

import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_context import reset_request_id, set_request_id


class RequestIdMiddleware:
    """Pure ASGI middleware — no response buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("X-Request-Id") or str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        # Bind into contextvar so every log record + downstream call
        # (carrier-gateway, stream publish) inherits the same trace id.
        token = set_request_id(request_id)

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append("X-Request-Id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            reset_request_id(token)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware — no response buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        from app.core.config import get_settings
        self._is_production = get_settings().is_production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                h["X-Content-Type-Options"] = "nosniff"
                h["X-Frame-Options"] = "DENY"
                h["X-XSS-Protection"] = "1; mode=block"
                h["Referrer-Policy"] = "strict-origin-when-cross-origin"
                h["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                if self._is_production:
                    h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                    h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                else:
                    h["Content-Security-Policy"] = (
                        "default-src 'self'; "
                        "script-src 'self' 'unsafe-inline'; "
                        "style-src 'self' 'unsafe-inline'; "
                        "img-src 'self' data:; "
                        "connect-src 'self'"
                    )
            await send(message)

        await self.app(scope, receive, _send)
