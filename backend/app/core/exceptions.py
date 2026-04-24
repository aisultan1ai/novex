from __future__ import annotations


class NovexException(Exception):
    """Base exception for all Novex application errors."""


class NotFoundError(NovexException):
    """Resource not found (HTTP 404)."""


class ConflictError(NovexException):
    """Resource already exists (HTTP 409)."""


class ValidationError(NovexException):
    """Business-logic validation failed (HTTP 422)."""


class UnauthorizedError(NovexException):
    """Authentication required or credentials invalid (HTTP 401)."""


class ForbiddenError(NovexException):
    """Authenticated user lacks permission (HTTP 403)."""