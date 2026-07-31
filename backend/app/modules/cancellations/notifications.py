"""Cancellation-specific notification fan-out.

Держим отдельно от общего NotificationsService: тип события
(«запрос от клиента / решение по заявке») не привязан к статусу заказа и
использует свой канал доставки email — на carrier.notification_email
через to_email_override, а не на user.email.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import insert as _sa_insert
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.streams import STREAM_EMAILS, publish
from app.modules.cancellations.models import CancellationRequest
from app.modules.carriers.models import Carrier
from app.modules.identity.models import CarrierProfile, Role, RoleCode, User
from app.modules.notifications.models import Notification as _Notification
from app.modules.notifications.repository import NotificationsRepository
from app.modules.orders.models import OrderDraft
from app.modules.shipments.models import Shipment

logger = logging.getLogger(__name__)

_notif_repo = NotificationsRepository()


# ── Public API ───────────────────────────────────────────────────────────

def notify_cancellation_created(
    db: Session,
    *,
    req: CancellationRequest,
    order_id: int,
) -> None:
    """Разослать уведомления при создании pending-заявки.

    Fan-out:
      • carrier ops mailbox (email) — если задан notification_email
      • carrier portal users (in-app) — все активные аккаунты перевозчика
      • admins (in-app) — только если API-фолбэк или у перевозчика нет
        notification_email (иначе админа в цикл не втягиваем)
    """
    order = db.get(OrderDraft, order_id)
    if order is None:
        logger.warning("notify_cancellation_created: order %s missing", order_id)
        return

    carrier = db.scalar(
        select(Carrier).where(Carrier.code == req.carrier_code)
    )
    customer = db.get(User, req.requested_by_user_id)

    # 1) Email на operational mailbox перевозчика (если задан).
    if carrier and carrier.notification_email:
        _publish_carrier_cancel_email(
            db,
            req=req,
            order=order,
            carrier=carrier,
            customer=customer,
        )

    # 2) In-app для пользователей перевозчика.
    carrier_user_ids = _list_carrier_user_ids(db, carrier_code=req.carrier_code)
    if carrier_user_ids:
        _bulk_notify(
            db,
            user_ids=carrier_user_ids,
            type="cancellation_incoming",
            title=f"Клиент запросил отмену заказа #{order.id}",
            body=f"Причина: {req.reason}",
            link_url=f"/dashboard/carrier/cancellation-requests/{req.id}",
        )

    # 3) Админам — только если фолбэк с API или нет ops-адреса перевозчика.
    escalate = req.api_attempted or not (carrier and carrier.notification_email)
    if escalate:
        admin_ids = _list_admin_user_ids(db)
        if admin_ids:
            title = f"Требуется помощь: заявка на отмену #{req.id}"
            body_parts = [f"Заказ #{order.id}, перевозчик {req.carrier_code}."]
            if req.api_attempted:
                body_parts.append(f"API-отмена не сработала: {req.api_error or 'unknown'}.")
            if not (carrier and carrier.notification_email):
                body_parts.append("У перевозчика не задан email для уведомлений.")
            _bulk_notify(
                db,
                user_ids=admin_ids,
                type="cancellation_needs_admin",
                title=title,
                body=" ".join(body_parts),
                link_url=f"/dashboard/admin/cancellation-requests/{req.id}",
            )

    # 4) In-app клиенту — подтверждение, что мы получили заявку.
    if customer:
        _notif_repo.create(
            db,
            user_id=customer.id,
            type="cancellation_requested",
            title=f"Заявка на отмену заказа #{order.id} отправлена",
            body="Ожидаем подтверждение перевозчика. Мы уведомим вас, как только будет решение.",
            link_url=f"/dashboard/orders/{order.id}",
        )

    db.commit()


def notify_cancellation_rejected(db: Session, *, req: CancellationRequest) -> None:
    """Клиент — заявка отклонена, заказ остаётся жить."""
    order = db.get(OrderDraft, req.order_draft_id)
    if order is None:
        return

    # In-app клиенту.
    _notif_repo.create(
        db,
        user_id=req.requested_by_user_id,
        type="cancellation_rejected",
        title=f"Заявка на отмену заказа #{order.id} отклонена",
        body=req.carrier_response or "Перевозчик отклонил заявку без комментария.",
        link_url=f"/dashboard/orders/{order.id}",
    )

    # Email клиенту через существующий stream — новый event_type.
    _publish_customer_email(
        user_id=req.requested_by_user_id,
        order_id=order.id,
        event_type="cancellation_rejected_to_customer",
        payload={
            "reason": req.reason,
            "carrier_response": req.carrier_response or "",
        },
    )
    db.commit()


# ── Internal helpers ─────────────────────────────────────────────────────

def _publish_carrier_cancel_email(
    db: Session,
    *,
    req: CancellationRequest,
    order: OrderDraft,
    carrier: Carrier,
    customer: User | None,
) -> None:
    """Отправка через STREAM_EMAILS с to_email_override → адрес перевозчика."""
    shipment = db.scalar(
        select(Shipment).where(Shipment.order_draft_id == order.id)
    )
    payload = {
        "carrier_name": carrier.name,
        "reason": req.reason,
        "tracking_number": (shipment.tracking_number if shipment else None) or "",
        "carrier_tracking_number": (
            (shipment.carrier_tracking_number if shipment else None) or ""
        ),
        "customer_email": customer.email if customer else "",
        "customer_phone": (customer.phone if customer else "") or "",
        "request_id": req.id,
    }
    try:
        publish(STREAM_EMAILS, {
            "user_id": "0",  # sentinel — consumer поймёт по to_email_override
            "order_id": str(order.id),
            "event_type": "cancellation_requested_to_carrier",
            "to_email_override": carrier.notification_email or "",
            "payload": json.dumps(payload, ensure_ascii=False),
        })
    except Exception:
        logger.exception(
            "Publish carrier-cancel email failed (non-fatal): request_id=%s carrier=%s",
            req.id, carrier.code,
        )


def _publish_customer_email(
    *,
    user_id: int,
    order_id: int,
    event_type: str,
    payload: dict,
) -> None:
    try:
        publish(STREAM_EMAILS, {
            "user_id": str(user_id),
            "order_id": str(order_id),
            "event_type": event_type,
            "payload": json.dumps(payload, ensure_ascii=False),
        })
    except Exception:
        logger.exception(
            "Publish customer email failed (non-fatal): user_id=%s event=%s",
            user_id, event_type,
        )


def _list_carrier_user_ids(db: Session, *, carrier_code: str) -> list[int]:
    return list(
        db.scalars(
            select(User.id)
            .join(CarrierProfile, CarrierProfile.user_id == User.id)
            .join(Carrier, Carrier.id == CarrierProfile.carrier_id)
            .where(Carrier.code == carrier_code, User.is_active.is_(True))
        ).all()
    )


def _list_admin_user_ids(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(User.id).join(User.role).where(
                Role.code == RoleCode.ADMIN,
                User.is_active.is_(True),
            )
        ).all()
    )


def _bulk_notify(
    db: Session,
    *,
    user_ids: list[int],
    type: str,
    title: str,
    body: str,
    link_url: str | None,
) -> None:
    if not user_ids:
        return
    db.execute(
        _sa_insert(_Notification),
        [
            {
                "user_id": uid,
                "type": type,
                "title": title,
                "body": body,
                "link_url": link_url,
                "is_read": False,
            }
            for uid in user_ids
        ],
    )
