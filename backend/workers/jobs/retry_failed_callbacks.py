from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.dispatch.models import DispatchJob, DispatchJobStatus
from app.modules.identity.models import Role, RoleCode, User
from app.modules.notifications.repository import NotificationsRepository

logger = logging.getLogger(__name__)

_LOOK_BACK_HOURS = 24
_repo = NotificationsRepository()


def run(db: Session) -> None:
    cutoff = datetime.utcnow() - timedelta(hours=_LOOK_BACK_HOURS)

    failed_jobs = db.scalars(
        select(DispatchJob)
        .where(
            DispatchJob.status == DispatchJobStatus.FAILED,
            DispatchJob.attempts >= DispatchJob.max_attempts,
            DispatchJob.created_at >= cutoff,
        )
        .order_by(DispatchJob.created_at.desc())
    ).all()

    if not failed_jobs:
        return

    logger.warning(
        "retry_failed_callbacks: %d permanently failed dispatch jobs found", len(failed_jobs)
    )

    admins = db.scalars(
        select(User)
        .join(User.role)
        .where(Role.code == RoleCode.ADMIN, User.is_active.is_(True))
    ).all()

    if not admins:
        logger.warning("retry_failed_callbacks: no active admins to notify")
        return

    order_ids = ", ".join(f"#{j.order_id}" for j in failed_jobs[:10])
    suffix = f" и ещё {len(failed_jobs) - 10}" if len(failed_jobs) > 10 else ""
    title = f"Ошибки диспетчеризации: {len(failed_jobs)} заказ(ов)"
    body = f"Не удалось передать перевозчику: {order_ids}{suffix}. Требуется ручная обработка."

    for admin in admins:
        _repo.create(db, user_id=admin.id, type="dispatch_failure_alert", title=title, body=body)

    db.commit()
    logger.info(
        "retry_failed_callbacks: notified %d admin(s) about %d failed dispatch jobs",
        len(admins),
        len(failed_jobs),
    )
