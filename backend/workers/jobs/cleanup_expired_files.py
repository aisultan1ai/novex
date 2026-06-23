from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.modules.notifications.models import NotificationJob
from app.modules.quotes.models import QuoteSession

logger = logging.getLogger(__name__)

_NOTIFICATION_JOB_RETENTION_DAYS = 7


def run(db: Session) -> None:
    now = datetime.utcnow()
    _delete_expired_quote_sessions(db, now)
    _delete_old_notification_jobs(db, now)
    db.commit()


def _delete_expired_quote_sessions(db: Session, now: datetime) -> None:
    result = db.execute(
        delete(QuoteSession).where(
            QuoteSession.expires_at.is_not(None),
            QuoteSession.expires_at < now,
        )
    )
    deleted = result.rowcount
    if deleted:
        logger.info("cleanup_expired_files: removed %d expired quote sessions", deleted)


def _delete_old_notification_jobs(db: Session, now: datetime) -> None:
    cutoff = now - timedelta(days=_NOTIFICATION_JOB_RETENTION_DAYS)
    result = db.execute(
        delete(NotificationJob).where(
            NotificationJob.status.in_(["sent", "failed"]),
            NotificationJob.created_at < cutoff,
        )
    )
    deleted = result.rowcount
    if deleted:
        logger.info("cleanup_expired_files: removed %d old notification jobs", deleted)
