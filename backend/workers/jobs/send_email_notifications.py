from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.modules.notifications.models import NotificationJob

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20
_LOCK_KEY = "lock:send_email_notifications"
_LOCK_TTL = 45  # seconds — must be < job interval (60s)


def run(db: Session) -> None:
    r = get_redis()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
        logger.debug("send_email_notifications: skipped — another replica holds the lock")
        return
    try:
        _run(db)
    finally:
        r.delete(_LOCK_KEY)


def _run(db: Session) -> None:
    now = datetime.utcnow()
    jobs = db.scalars(
        select(NotificationJob)
        .where(
            NotificationJob.status.in_(["pending", "failed"]),
            NotificationJob.channel == "email",
            NotificationJob.attempts < NotificationJob.max_attempts,
            (NotificationJob.next_retry_at.is_(None))
            | (NotificationJob.next_retry_at <= now),
        )
        .order_by(NotificationJob.created_at.asc())
        .limit(_BATCH_SIZE)
    ).all()

    if not jobs:
        return

    logger.info("send_email_notifications: processing %d jobs", len(jobs))
    for job in jobs:
        _process(db, job)


def _process(db: Session, job: NotificationJob) -> None:
    job.status = "processing"
    job.attempts += 1
    db.flush()

    try:
        payload = json.loads(job.payload) if job.payload else {}
        _deliver(db, job, payload)
        job.status = "sent"
        job.sent_at = datetime.utcnow()
        job.last_error = None
        logger.info("send_email_notifications: job %d sent (user_id=%d)", job.id, job.user_id)
    except Exception as exc:
        logger.warning("send_email_notifications: job %d attempt %d failed: %s", job.id, job.attempts, exc)
        job.last_error = str(exc)
        job.status = "failed"
        if job.attempts < job.max_attempts:
            job.next_retry_at = datetime.utcnow() + timedelta(minutes=5 * job.attempts)

    db.commit()


def _deliver(db: Session, job: NotificationJob, payload: dict) -> None:
    from app.core.email import send_email
    from app.core.email_templates import order_status_email
    from app.modules.identity.models import User

    user = db.get(User, job.user_id)
    if not user or not user.email:
        logger.warning("send_email_notifications: no email for user_id=%d, skipping", job.user_id)
        return

    if job.order_id is None:
        return
    result = order_status_email(
        job.event_type,
        job.order_id,
        user_name=user.full_name,
        reject_reason=payload.get("reject_reason"),
    )
    if result is None:
        return

    subject, html_body = result
    send_email(to=user.email, subject=subject, html=html_body)
