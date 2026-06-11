from __future__ import annotations

import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, **kwargs) -> None:
        super().__init__(app, **kwargs)
        from app.core.config import get_settings
        self._is_production = get_settings().is_production

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if self._is_production:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            )
        return response
