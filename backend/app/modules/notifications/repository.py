from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification


class NotificationsRepository:
    def create(
        self,
        db: Session,
        *,
        user_id: int,
        type: str,
        title: str,
        body: str | None = None,
    ) -> Notification:
        n = Notification(user_id=user_id, type=type, title=title, body=body)
        db.add(n)
        db.flush()
        return n

    def list_for_user(
        self,
        db: Session,
        *,
        user_id: int,
        limit: int = 50,
    ) -> Sequence[Notification]:
        return db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()

    def count_unread(self, db: Session, *, user_id: int) -> int:
        return db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        ) or 0

    def mark_read(self, db: Session, *, notification_id: int, user_id: int) -> bool:
        result = db.execute(
            sa_update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(is_read=True)
        )
        return result.rowcount > 0

    def mark_all_read(self, db: Session, *, user_id: int) -> int:
        result = db.execute(
            sa_update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        return result.rowcount
