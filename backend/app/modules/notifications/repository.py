from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.i18n import Bi, resolve
from app.modules.notifications.models import Notification


logger = logging.getLogger(__name__)


def user_locales(db: Session, user_ids: Sequence[int]) -> dict[int, str]:
    """{user_id: "ru" | "kk"} для получателей уведомлений. Безопасно для
    транзакций обработки статусов: SAVEPOINT + фолбэк на русский при ошибке."""
    from app.modules.identity.models import User

    ids = list({uid for uid in user_ids if uid is not None})
    if not ids:
        return {}
    # Сначала сбрасываем ожидающие изменения вызывающего кода (как сделал бы
    # autoflush), чтобы их возможная ошибка не была проглочена ниже.
    db.flush()
    try:
        with db.begin_nested():
            rows = db.execute(select(User.id, User.locale).where(User.id.in_(ids))).all()
    except Exception:
        logger.warning("Не удалось получить язык пользователей %s — уведомления будут на русском", ids, exc_info=True)
        return {}
    return {uid: (loc if loc in ("ru", "kk") else "ru") for uid, loc in rows}


class NotificationsRepository:
    def create(
        self,
        db: Session,
        *,
        user_id: int,
        type: str,
        title: str | Bi,
        body: str | Bi | None = None,
        link_url: str | None = None,
    ) -> Notification:
        # Bi(ru, kk) → текст на языке получателя (users.locale).
        locale = self.user_locale(db, user_id) if isinstance(title, Bi) or isinstance(body, Bi) else None
        n = Notification(
            user_id=user_id,
            type=type,
            title=resolve(title, locale),
            body=resolve(body, locale),
            link_url=link_url,
        )
        db.add(n)
        db.flush()
        return n

    @staticmethod
    def user_locale(db: Session, user_id: int) -> str:
        """Язык получателя уведомления (users.locale), по умолчанию "ru".

        Вызывается внутри обработки статусов (вебхук перевозчика, polling,
        dispatch), часто в ТОЙ ЖЕ транзакции, что и смена статуса. Поэтому
        запрос идёт в SAVEPOINT и любые ошибки гасятся: язык уведомления не
        должен откатить обновление статуса заказа.
        """
        return user_locales(db, [user_id]).get(user_id, "ru")

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
        return (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.is_read.is_(False),
                )
            )
            or 0
        )

    def mark_read(self, db: Session, *, notification_id: int, user_id: int) -> bool:
        result: CursorResult = db.execute(  # type: ignore[assignment]
            sa_update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(is_read=True)
        )
        return result.rowcount > 0

    def mark_all_read(self, db: Session, *, user_id: int) -> int:
        result: CursorResult = db.execute(  # type: ignore[assignment]
            sa_update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        return result.rowcount
