from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
)

logger = logging.getLogger(__name__)

_STATUS_TITLES: dict[str, str] = {
    "paid": "Оплата подтверждена",
    "awaiting_payment": "Ожидание оплаты",
    "payment_under_review": "Чек на проверке",
    "payment_rejected": "Чек отклонён - требуется повторная оплата",
    "ready_for_checkout": "Готов к оформлению",
    "sent_to_carrier": "Передан перевозчику",
    "picked_up": "Забран перевозчиком",
    "in_transit": "В пути",
    "arrived": "Прибыл в пункт выдачи",
    "delivered": "Доставлен",
    "cancelled": "Отменён",
    "refunded": "Средства возвращены",
    "return": "Возврат",
    "return_requested": "Запрошен возврат",
    "return_in_progress": "Возврат в пути",
    "returned": "Возвращён",
    "dispatched": "Заказ передан перевозчику",
    "dispatch_queued": "Заказ поставлен в очередь на отправку",
    "dispatch_failed": "Заказ оформлен, уточняем детали доставки",
    # Оба pending_manual* для клиента звучат одинаково — внутренняя разница
    # (нет API у перевозчика vs требуется ручной push) видна только админам.
    "pending_manual": "Заказ оформлен, передаётся перевозчику",
    "pending_manual_dispatch": "Заказ оформлен, передаётся перевозчику",
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
        reject_reason: str | None = None,
        tracking_number: str | None = None,
    ) -> None:
        title = _STATUS_TITLES.get(status, f"Статус обновлён: {status}")
        # sent_to_carrier — момент когда у нас впервые есть трек-номер:
        # клиенту важно увидеть его в push/центре уведомлений вместе с
        # инструкцией «ждите звонка курьера», без перехода на страницу заказа.
        if status == "sent_to_carrier" and tracking_number:
            body = (
                f"Заказ #{order_id} передан перевозчику. "
                f"Ожидайте звонка курьера. Трек-номер: {tracking_number}"
            )
        else:
            body = f"Заказ #{order_id}: {title.lower()}"
        # Payment-adjacent statuses take the user to /checkout so they land on
        # the pay/upload-proof screen instead of the read-only order card.
        # Everything else routes to the order detail page.
        _PAYMENT_STATUSES = {"awaiting_payment", "payment_rejected", "ready_for_checkout"}
        link_url = (
            f"/checkout?draftId={order_id}"
            if status in _PAYMENT_STATUSES
            else f"/dashboard/orders/{order_id}"
        )
        self.repo.create(
            db,
            user_id=user_id,
            type="order_status",
            title=title,
            body=body,
            link_url=link_url,
        )
        logger.info(
            "Notification sent: user_id=%s order_id=%s status=%s",
            user_id,
            order_id,
            status,
        )

        self._send_order_email(
            db,
            user_id=user_id,
            order_id=order_id,
            status=status,
            reject_reason=reject_reason,
            tracking_number=tracking_number,
        )

    def _send_order_email(
        self,
        db: Session,
        *,
        user_id: int,
        order_id: int,
        status: str,
        reject_reason: str | None = None,
        tracking_number: str | None = None,
    ) -> None:
        import json

        from app.core.streams import STREAM_EMAILS, publish

        payload: dict[str, str] = {}
        if reject_reason:
            payload["reject_reason"] = reject_reason
        if tracking_number:
            payload["tracking_number"] = tracking_number

        try:
            publish(STREAM_EMAILS, {
                "user_id": str(user_id),
                "order_id": str(order_id),
                "event_type": status,
                "payload": json.dumps(payload),
            })
            logger.info(
                "Email queued to stream: user_id=%s order_id=%s status=%s",
                user_id, order_id, status,
            )
        except Exception:
            logger.exception(
                "Failed to queue email (non-fatal): user_id=%s order_id=%s status=%s",
                user_id, order_id, status,
            )

    def list_notifications(
        self, db: Session, *, user_id: int
    ) -> NotificationListResponse:
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
