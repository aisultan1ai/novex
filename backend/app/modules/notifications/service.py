from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.schemas import NotificationListResponse, NotificationResponse

logger = logging.getLogger(__name__)

_STATUS_TITLES: dict[str, str] = {
    "paid": "Оплата подтверждена",
    "awaiting_payment": "Ожидание оплаты",
    "ready_for_checkout": "Готов к оформлению",
    "sent_to_carrier": "Передан перевозчику",
    "picked_up": "Забран перевозчиком",
    "in_transit": "В пути",
    "arrived": "Прибыл в пункт выдачи",
    "delivered": "Доставлен",
    "cancelled": "Отменён",
    "return": "Возврат",
}


class NotificationsService:
    def __init__(self, repo: NotificationsRepository | None = None) -> None:
        self.repo = repo or NotificationsRepository()

    def notify_order_status(
        self,
        db: Session,
        *,
        user_id: int,
        order_id: int,
        status: str,
    ) -> None:
        title = _STATUS_TITLES.get(status, f"Статус обновлён: {status}")
        body = f"Заказ #{order_id}: {title.lower()}"
        self.repo.create(db, user_id=user_id, type="order_status", title=title, body=body)
        logger.info("Notification sent: user_id=%s order_id=%s status=%s", user_id, order_id, status)

    def list_notifications(self, db: Session, *, user_id: int) -> NotificationListResponse:
        items = self.repo.list_for_user(db, user_id=user_id)
        unread = self.repo.count_unread(db, user_id=user_id)
        return NotificationListResponse(
            items=[NotificationResponse.model_validate(n) for n in items],
            unread_count=unread,
        )

    def mark_read(self, db: Session, *, notification_id: int, user_id: int) -> None:
        self.repo.mark_read(db, notification_id=notification_id, user_id=user_id)
        db.commit()

    def mark_all_read(self, db: Session, *, user_id: int) -> int:
        count = self.repo.mark_all_read(db, user_id=user_id)
        db.commit()
        return count
