"""Time helpers.

`utcnow()` returns a naive UTC datetime — matches every existing
`TIMESTAMP WITHOUT TIME ZONE` column in the schema. Use this instead of
`datetime.utcnow()` (deprecated in Python 3.12+) or ad-hoc
`datetime.now(UTC).replace(tzinfo=None)` sprinkled across services.
"""
from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC datetime — DB-column-compatible."""
    return datetime.now(UTC).replace(tzinfo=None)
