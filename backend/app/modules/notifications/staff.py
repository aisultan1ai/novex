"""Email alerts for staff (admins + operators) — audit 2026-10-04, T7.

Events that need a human to act: a payment proof to check, a cancellation
request to decide, an order the dispatcher gave up on. Delivered through the
regular email stream (SMTP worker) with ``to_email_override`` per recipient.

Never raises: a failed alert must not break the action that triggered it.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.streams import STREAM_EMAILS, publish
from app.modules.identity.models import Role, RoleCode, User

logger = logging.getLogger(__name__)

STAFF_EVENTS = ("payment_proof", "cancellation_request", "dispatch_failed")


def _staff_emails(db: Session) -> list[str]:
    return [
        email
        for email in db.scalars(
            select(User.email).join(User.role).where(
                Role.code.in_((RoleCode.ADMIN, RoleCode.OPERATOR)),
                User.is_active.is_(True),
            )
        ).all()
        if email
    ]


def notify_staff(
    db: Session,
    *,
    event: str,
    order_id: int,
    payload: dict[str, str] | None = None,
) -> None:
    """Queue one email per active admin/operator. ``event`` is one of STAFF_EVENTS."""
    if event not in STAFF_EVENTS:
        logger.error("notify_staff: unknown event %r", event)
        return
    try:
        recipients = _staff_emails(db)
        body = json.dumps(payload or {}, ensure_ascii=False)
        for email in recipients:
            publish(STREAM_EMAILS, {
                "user_id": "0",
                "order_id": str(order_id),
                "event_type": f"staff_{event}",
                "payload": body,
                "to_email_override": email,
            })
        logger.info(
            "notify_staff: %s for order %s queued to %d recipient(s)",
            event, order_id, len(recipients),
        )
    except Exception:
        logger.exception("notify_staff: failed to queue %s for order %s (non-fatal)", event, order_id)
