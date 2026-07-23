from __future__ import annotations

import json
import logging
import socket
from threading import Event

from app.core.redis import get_redis
from app.core.request_context import bind_request_id
from app.core.streams import GROUP_EMAILS, REQUEST_ID_FIELD, STREAM_EMAILS

logger = logging.getLogger(__name__)

_CONSUMER_NAME = f"email-{socket.gethostname()}"


def run(stop_event: Event) -> None:
    r = get_redis()
    logger.info("Email consumer started (group=%s consumer=%s)", GROUP_EMAILS, _CONSUMER_NAME)
    _recover_pending(r)

    while not stop_event.is_set():
        try:
            entries = r.xreadgroup(
                GROUP_EMAILS,
                _CONSUMER_NAME,
                {STREAM_EMAILS: ">"},
                count=10,
                block=5000,
            )
        except Exception:
            logger.exception("Email consumer: xreadgroup error, retrying in 2s")
            stop_event.wait(2)
            continue

        if not entries:
            continue

        for _, messages in entries:  # type: ignore[union-attr]
            for msg_id, data in messages:
                with bind_request_id(data.get(REQUEST_ID_FIELD)):
                    try:
                        _process(data)
                        r.xack(STREAM_EMAILS, GROUP_EMAILS, msg_id)
                    except Exception:
                        logger.exception("Email consumer: msg %s failed, left in PEL for recovery", msg_id)


def _recover_pending(r) -> None:
    """Process messages left pending by a previous crashed consumer instance."""
    entries = r.xreadgroup(GROUP_EMAILS, _CONSUMER_NAME, {STREAM_EMAILS: "0-0"}, count=100)
    if not entries:
        return
    for _, messages in entries:
        for msg_id, data in messages:
            with bind_request_id(data.get(REQUEST_ID_FIELD)):
                try:
                    _process(data)
                except Exception:
                    logger.exception("Email consumer: pending msg %s failed, skipping", msg_id)
                finally:
                    r.xack(STREAM_EMAILS, GROUP_EMAILS, msg_id)


def _process(data: dict) -> None:
    from app.core.db import SessionLocal
    from app.core.email import send_email
    from app.core.email_templates import order_status_email
    from app.modules.identity.models import User

    user_id = int(data["user_id"])
    order_id = int(data["order_id"])
    event_type = data["event_type"]
    payload = json.loads(data.get("payload", "{}"))

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user or not user.email:
            logger.warning("Email consumer: no email for user_id=%d, skipping", user_id)
            return

        rendered = order_status_email(
            event_type,
            order_id,
            user_name=user.full_name,
            reject_reason=payload.get("reject_reason"),
        )
        if rendered is None:
            return

        subject, html_body = rendered
        send_email(to=user.email, subject=subject, html=html_body)
        logger.info(
            "Email consumer: sent user_id=%d order_id=%d event=%s",
            user_id,
            order_id,
            event_type,
        )
