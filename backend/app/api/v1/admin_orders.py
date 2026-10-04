from __future__ import annotations

import logging
import math
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.status_machine import can_transition
from app.core.db import get_db
from app.core.dependencies import require_admin, require_admin_or_operator
from app.core.excel import build_xlsx_response, fmt_dt
from app.core.limiter import limiter
from app.modules.audit.service import AuditService
from app.modules.cancellations.repository import CancellationRequestsRepository
from app.modules.commissions.service import CommissionsService
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.dispatch.service import DispatchWorker
from app.modules.identity.models import User
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft
from app.modules.shipments.repository import ShipmentsRepository
from app.modules.shipments.service import ShipmentsService
from app.modules.tracking.repository import TrackingRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/orders", tags=["admin:orders"])

_notifications_svc = NotificationsService()
_tracking_repo = TrackingRepository()
_shipments_repo = ShipmentsRepository()
_shipments_svc = ShipmentsService()
_dispatch_svc = DispatchWorker()
_audit_svc = AuditService()
_commissions_svc = CommissionsService()
_cancel_repo = CancellationRequestsRepository()

# Держим синхронно с OrderDraftStatus Literal (backend/app/modules/orders/schemas.py)
# и ALLOWED_ORDER_TRANSITIONS (backend/app/common/status_machine.py). Пропустишь
# статус — админ не сможет выставить его вручную даже когда система уже его
# знает (например, customs_hold приходит через carrier_tracking автоматически).
VALID_STATUSES = {
    "draft",
    "shipment_details_completed",
    "ready_for_checkout",
    "awaiting_payment",
    "payment_under_review",
    "payment_rejected",
    "paid",
    "dispatch_queued",
    "dispatch_failed",
    "pending_manual",
    "pending_manual_dispatch",
    "sent_to_carrier",
    "picked_up",
    "in_transit",
    "out_for_delivery",
    "arrived",
    "delivered",
    "delivery_failed",
    "customs_hold",
    "return_requested",
    "return_in_progress",
    "returned",
    "cancelled",
}


class OrderStatusUpdate(BaseModel):
    status: str


class MarkDispatchedPayload(BaseModel):
    tracking_number: str


@router.get("/dispatch-queue")
def get_dispatch_queue(
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    stmt = (
        select(OrderDraft)
        .where(OrderDraft.status.in_(["dispatch_failed", "pending_manual"]))
        .order_by(OrderDraft.created_at.desc())
    )
    orders = db.scalars(stmt).all()
    items = [
        {
            "id": o.id,
            "carrier_code_snapshot": o.carrier_code_snapshot,
            "carrier_name_snapshot": o.carrier_name_snapshot,
            "status": o.status,
            "dispatch_error": o.dispatch_error,
            "created_at": o.created_at.isoformat(),
            "updated_at": o.updated_at.isoformat(),
        }
        for o in orders
    ]
    return {"items": items, "total": len(items)}


# Declared before "/{order_id}" so "counters" is not parsed as an order id.
@router.get("/counters")
def get_work_counters(
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    """Counters for the admin / operator workspace (audit 2026-10-04, T6)."""
    from datetime import timedelta

    from app.common.time_utils import utcnow
    from app.modules.cancellations.models import CancellationRequest
    from app.modules.dispatch.models import DispatchJob, DispatchJobStatus

    def _count_orders(*statuses: str) -> int:
        return db.scalar(
            select(func.count()).select_from(OrderDraft).where(OrderDraft.status.in_(statuses))
        ) or 0

    # A job claimed for longer than this is no longer "in progress": the
    # worker died mid-call and the job needs a human (see DispatchWorker T2).
    stuck_before = utcnow() - timedelta(minutes=10)

    return {
        "payment_review": _count_orders("payment_under_review"),
        "awaiting_dispatch": _count_orders("paid", "dispatch_queued"),
        "dispatch_failed": _count_orders("dispatch_failed"),
        "cancellation_pending": db.scalar(
            select(func.count()).select_from(CancellationRequest)
            .where(CancellationRequest.status == "pending")
        ) or 0,
        "orphan_waybills": db.scalar(
            select(func.count()).select_from(OrderDraft)
            .where(OrderDraft.orphan_waybill_number.is_not(None))
        ) or 0,
        "stuck_dispatch_jobs": db.scalar(
            select(func.count()).select_from(DispatchJob).where(
                DispatchJob.status == DispatchJobStatus.PROCESSING,
                DispatchJob.updated_at < stuck_before,
            )
        ) or 0,
    }


@router.get("")
@limiter.limit("120/minute")
def list_all_orders(
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="One status or a comma-separated list"),
    user_id: int | None = Query(default=None),
    order_id: int | None = Query(default=None),
    orphan_waybill: bool = Query(default=False, description="Only orders with a leftover waybill (T3)"),
    barcode: str | None = Query(default=None, description="Substring match on carrier barcode / tracking numbers"),
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    from app.modules.shipments.models import Shipment as _Shipment

    stmt = select(OrderDraft).order_by(OrderDraft.created_at.desc())
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        stmt = stmt.where(OrderDraft.status.in_(statuses))
    if order_id:
        stmt = stmt.where(OrderDraft.id == order_id)
    if orphan_waybill:
        stmt = stmt.where(OrderDraft.orphan_waybill_number.is_not(None))
    if user_id:
        stmt = stmt.where(OrderDraft.user_id == user_id)
    if barcode:
        # Match any of the three identifiers admin might scan / type:
        #  · Novex tracking_number (CSE-ABC123..., customer-facing)
        #  · carrier_tracking_number (Exline orderno / CSE order number)
        #  · carrier_barcode (physical scannable code on package)
        needle = f"%{barcode.strip()}%"
        stmt = stmt.join(_Shipment, _Shipment.order_draft_id == OrderDraft.id).where(
            (_Shipment.tracking_number.ilike(needle))
            | (_Shipment.carrier_tracking_number.ilike(needle))
            | (_Shipment.carrier_barcode.ilike(needle))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    orders = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()

    user_ids = {o.user_id for o in orders}
    users_map: dict[int, User] = {}
    if user_ids:
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u for u in users}

    order_ids = [o.id for o in orders]
    shipments_map: dict[int, _Shipment] = {}
    if order_ids:
        shps = db.scalars(select(_Shipment).where(_Shipment.order_draft_id.in_(order_ids))).all()
        shipments_map = {s.order_draft_id: s for s in shps}

    # Preload customer-cancel events + reasons for the visible page in one query
    # so the list can show "отмена клиентом" flags without an N+1.
    cancel_map: dict[int, dict] = {}
    if order_ids:
        cancel_rows = db.scalars(
            select(OrderStatusHistory)
            .where(
                OrderStatusHistory.order_id.in_(order_ids),
                OrderStatusHistory.new_status == "cancelled",
            )
            .order_by(OrderStatusHistory.created_at.desc())
        ).all()
        for row in cancel_rows:
            if row.order_id not in cancel_map:
                cancel_map[row.order_id] = {
                    "reason": row.comment or "Причина не указана",
                    "source": row.source,
                    "cancelled_at": row.created_at.isoformat(),
                }

    # Один запрос на страницу — чтобы в списке рядом со статусом показать
    # badge «Заявка на отмену» без N+1.
    pending_cancel_ids = _cancel_repo.order_ids_with_pending(db, order_ids)

    items = [
        {
            "id": o.id,
            "status": o.status,
            "user_id": o.user_id,
            "user_email": users_map[o.user_id].email
            if o.user_id in users_map
            else None,
            "user_name": users_map[o.user_id].full_name
            if o.user_id in users_map
            else None,
            "from_city": o.from_city_snapshot,
            "to_city": o.to_city_snapshot,
            "carrier_name": o.carrier_name_snapshot,
            "carrier_code": o.carrier_code_snapshot,
            "tariff_name": o.tariff_name_snapshot,
            "price": float(o.price_snapshot),
            # carrier_price: what perevozchik receives. Falls back to price for
            # legacy rows created before migration 032 introduced the split.
            "carrier_price": (
                float(o.carrier_price_snapshot)
                if o.carrier_price_snapshot is not None
                else float(o.price_snapshot)
            ),
            "markup_amount": (
                float(o.markup_amount_snapshot) if o.markup_amount_snapshot is not None else 0.0
            ),
            "currency": o.currency_snapshot,
            "created_at": o.created_at.isoformat(),
            "tracking_number": shipments_map[o.id].tracking_number if o.id in shipments_map else None,
            "carrier_tracking_number": shipments_map[o.id].carrier_tracking_number if o.id in shipments_map else None,
            "carrier_barcode": shipments_map[o.id].carrier_barcode if o.id in shipments_map else None,
            "cancellation": cancel_map.get(o.id),
            "has_pending_cancellation": o.id in pending_cancel_ids,
        }
        for o in orders
    ]

    pages = math.ceil(total / size) if total > 0 else 1
    logger.debug("admin list_all_orders: page=%d size=%d total=%d", page, size, total)
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


_STATUS_LABELS_RU: dict[str, str] = {
    "draft": "Черновик",
    "shipment_details_completed": "Данные заполнены",
    "ready_for_checkout": "Готов к оплате",
    "awaiting_payment": "Ожидает оплату",
    "payment_under_review": "Оплата на проверке",
    "payment_rejected": "Оплата отклонена",
    "paid": "Оплачен",
    "dispatch_queued": "В очереди на отправку",
    "dispatch_failed": "Ошибка отправки",
    "pending_manual": "Ручная обработка",
    "pending_manual_dispatch": "Ручная отправка",
    "sent_to_carrier": "Передан перевозчику",
    "picked_up": "Забран курьером",
    "in_transit": "В пути",
    "out_for_delivery": "Передан курьеру доставки",
    "arrived": "Прибыл",
    "delivered": "Доставлен",
    "delivery_failed": "Не удалось доставить",
    "customs_hold": "На таможне",
    "return_requested": "Запрошен возврат",
    "return_in_progress": "Возврат в процессе",
    "returned": "Возвращён",
    "cancelled": "Отменён",
}


def _party_by_role(parties: list, role: str) -> object | None:
    for p in parties:
        if p.role == role:
            return p
    return None


def _party_address(p) -> str:
    if not p:
        return ""
    parts = [p.city, p.address_line1]
    if p.address_line2:
        parts.append(p.address_line2)
    if p.postal_code:
        parts.append(p.postal_code)
    return ", ".join(x for x in parts if x)


_ORDER_EXPORT_HEADERS = [
    "ID заказа",
    "Дата создания",
    "Дата обновления",
    "Статус",
    "Клиент (email)",
    "Клиент (имя)",
    "Откуда (город)",
    "Куда (город)",
    "Тип отправления",
    "Перевозчик",
    "Код перевозчика",
    "Тариф",
    "Срок (мин, дн.)",
    "Срок (макс, дн.)",
    "Цена клиенту",
    "Стоимость перевозки",
    "Наценка Novex",
    "Валюта",
    "Трек Novex",
    "Трек перевозчика",
    "Штрих-код",
    "Отправитель ФИО",
    "Отправитель телефон",
    "Отправитель компания",
    "Отправитель ИИН/БИН",
    "Отправитель адрес",
    "Получатель ФИО",
    "Получатель телефон",
    "Получатель компания",
    "Получатель ИИН/БИН",
    "Получатель адрес",
    "Мест",
    "Вес суммарный, кг",
    "Габариты (Ш×В×Г см)",
    "Страхование",
    "Хрупкий груз",
    "Звонок перед доставкой",
    "Вызов курьера",
    "Дата вывоза",
    "Слот вывоза",
    "Ошибка отправки",
]


def _order_to_export_row(order: OrderDraft, user: User | None, shipment) -> list:
    parties = list(order.parties)
    packages = list(order.packages)
    sender = _party_by_role(parties, "sender")
    recipient = _party_by_role(parties, "recipient")

    total_qty = sum(int(p.quantity or 0) for p in packages)
    total_weight = sum(float(p.weight_kg or 0) for p in packages)
    dims = "; ".join(
        f"{p.width_cm:g}×{p.height_cm:g}×{p.depth_cm:g}" for p in packages
    ) if packages else ""

    return [
        order.id,
        fmt_dt(order.created_at),
        fmt_dt(order.updated_at),
        _STATUS_LABELS_RU.get(order.status, order.status),
        user.email if user else None,
        user.full_name if user else None,
        order.from_city_snapshot,
        order.to_city_snapshot,
        "Посылка" if order.shipment_type_snapshot == "parcel" else "Документ",
        order.carrier_name_snapshot,
        order.carrier_code_snapshot,
        order.tariff_name_snapshot,
        order.eta_days_min_snapshot,
        order.eta_days_max_snapshot,
        float(order.price_snapshot) if order.price_snapshot is not None else None,
        float(order.carrier_price_snapshot) if order.carrier_price_snapshot is not None else None,
        float(order.markup_amount_snapshot) if order.markup_amount_snapshot is not None else None,
        order.currency_snapshot,
        shipment.tracking_number if shipment else None,
        shipment.carrier_tracking_number if shipment else None,
        shipment.carrier_barcode if shipment else None,
        sender.full_name if sender else None,
        sender.phone if sender else None,
        sender.company_name if sender else None,
        sender.tax_id if sender else None,
        _party_address(sender),
        recipient.full_name if recipient else None,
        recipient.phone if recipient else None,
        recipient.company_name if recipient else None,
        recipient.tax_id if recipient else None,
        _party_address(recipient),
        total_qty,
        round(total_weight, 3) if total_weight else 0,
        dims,
        "да" if order.insurance else "нет",
        "да" if order.fragile else "нет",
        "да" if order.call_before_delivery else "нет",
        "да" if order.pickup_requested else "нет",
        order.pickup_date,
        order.pickup_time_slot,
        order.dispatch_error,
    ]


@router.get("/export", summary="Экспорт заказов в Excel")
@limiter.limit("10/hour")
def export_orders(
    request: Request,
    status: str | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    barcode: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
):
    """XLSX-выгрузка заказов с теми же фильтрами, что и список.

    Rate-limit: 10 экспортов в час на IP. Хард-кап MAX_EXPORT_ROWS (50k)
    защищает от «выгрузить всё за 3 года».
    """
    from app.modules.shipments.models import Shipment as _Shipment

    stmt = (
        select(OrderDraft)
        .options(
            selectinload(OrderDraft.parties),
            selectinload(OrderDraft.packages),
        )
        .order_by(OrderDraft.created_at.desc())
    )
    if status:
        stmt = stmt.where(OrderDraft.status == status)
    if carrier_code:
        stmt = stmt.where(OrderDraft.carrier_code_snapshot == carrier_code)
    if date_from:
        stmt = stmt.where(OrderDraft.created_at >= date_from)
    if date_to:
        stmt = stmt.where(OrderDraft.created_at <= date_to)
    if barcode:
        needle = f"%{barcode.strip()}%"
        stmt = stmt.join(_Shipment, _Shipment.order_draft_id == OrderDraft.id).where(
            (_Shipment.tracking_number.ilike(needle))
            | (_Shipment.carrier_tracking_number.ilike(needle))
            | (_Shipment.carrier_barcode.ilike(needle))
        )

    orders = db.scalars(stmt).all()
    if not orders:
        raise HTTPException(422, "По этим фильтрам нет заказов для экспорта")

    user_ids = {o.user_id for o in orders}
    users_map: dict[int, User] = {}
    if user_ids:
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u for u in users}

    order_ids = [o.id for o in orders]
    shipments_map: dict[int, _Shipment] = {}
    if order_ids:
        shps = db.scalars(select(_Shipment).where(_Shipment.order_draft_id.in_(order_ids))).all()
        shipments_map = {s.order_draft_id: s for s in shps}

    rows = (
        _order_to_export_row(o, users_map.get(o.user_id), shipments_map.get(o.id))
        for o in orders
    )
    # Итоги: сумма по трём денежным колонкам (15, 16, 17).
    total_price = sum(
        float(o.price_snapshot) for o in orders if o.price_snapshot is not None
    )
    total_carrier = sum(
        float(o.carrier_price_snapshot) for o in orders
        if o.carrier_price_snapshot is not None
    )
    total_markup = sum(
        float(o.markup_amount_snapshot) for o in orders
        if o.markup_amount_snapshot is not None
    )
    total_row: list = [None] * len(_ORDER_EXPORT_HEADERS)
    total_row[0] = f"Итого: {len(orders)} строк"
    total_row[14] = total_price
    total_row[15] = total_carrier
    total_row[16] = total_markup

    return build_xlsx_response(
        filename_base="orders_admin",
        sheet_name="Заказы",
        headers=_ORDER_EXPORT_HEADERS,
        rows=rows,
        money_cols=[15, 16, 17],
        datetime_cols=[2, 3],
        date_cols=[39],
        total_row=total_row,
    )


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    order = db.scalar(
        select(OrderDraft)
        .options(
            selectinload(OrderDraft.parties),
            selectinload(OrderDraft.packages),
        )
        .where(OrderDraft.id == order_id)
    )
    if not order:
        raise HTTPException(404, "Заказ не найден")

    user = db.get(User, order.user_id)
    from app.modules.shipments.models import Shipment as _Shipment
    shipment = db.scalar(select(_Shipment).where(_Shipment.order_draft_id == order_id))

    # Cancellation details — read the most recent cancel event from OrderStatusHistory.
    # `source` distinguishes customer_cancel vs admin vs system_worker.
    cancel_event = db.scalar(
        select(OrderStatusHistory)
        .where(
            OrderStatusHistory.order_id == order_id,
            OrderStatusHistory.new_status == "cancelled",
        )
        .order_by(OrderStatusHistory.created_at.desc())
        .limit(1)
    )
    cancellation: dict | None = None
    if cancel_event:
        cancelled_by_user = (
            db.get(User, cancel_event.changed_by_user_id)
            if cancel_event.changed_by_user_id else None
        )
        cancellation = {
            "reason": cancel_event.comment or "Причина не указана",
            "cancelled_at": cancel_event.created_at.isoformat(),
            "source": cancel_event.source,
            "cancelled_by_email": cancelled_by_user.email if cancelled_by_user else None,
            "cancelled_by_name": cancelled_by_user.full_name if cancelled_by_user else None,
        }

    # Refund status — take the latest PaymentTransaction. Customer cancel sets
    # it to refund_pending; admin refund flips to refunded.
    from app.modules.payments.transaction_models import PaymentTransaction
    latest_tx = db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.order_id == order_id)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(1)
    )
    refund_status: str | None = None
    if latest_tx:
        tx_status = latest_tx.status.value if hasattr(latest_tx.status, "value") else str(latest_tx.status)
        if tx_status in ("refund_pending", "refunded"):
            refund_status = tx_status

    # Активная (pending) заявка на отмену — показывается прямо в карточке
    # заказа, чтобы админ мог принять решение без перехода на отдельный экран.
    pending_cancel = _cancel_repo.get_pending_for_order(db, order_id)
    cancellation_request: dict | None = None
    if pending_cancel:
        cancellation_request = {
            "id": pending_cancel.id,
            "status": pending_cancel.status,
            "reason": pending_cancel.reason,
            "carrier_code": pending_cancel.carrier_code,
            "api_attempted": pending_cancel.api_attempted,
            "api_error": pending_cancel.api_error,
            "carrier_response": pending_cancel.carrier_response,
            "created_at": pending_cancel.created_at.isoformat(),
        }

    return {
        "id": order.id,
        "status": order.status,
        "user_id": order.user_id,
        "user_email": user.email if user else None,
        "user_name": user.full_name if user else None,
        "from_city": order.from_city_snapshot,
        "to_city": order.to_city_snapshot,
        "carrier_name": order.carrier_name_snapshot,
        "tariff_name": order.tariff_name_snapshot,
        "price": float(order.price_snapshot),
        "carrier_price": (
            float(order.carrier_price_snapshot)
            if order.carrier_price_snapshot is not None
            else float(order.price_snapshot)
        ),
        "markup_amount": (
            float(order.markup_amount_snapshot) if order.markup_amount_snapshot is not None else 0.0
        ),
        "currency": order.currency_snapshot,
        "eta_days_min": order.eta_days_min_snapshot,
        "eta_days_max": order.eta_days_max_snapshot,
        "shipment_type": order.shipment_type_snapshot,
        "carrier_code": order.carrier_code_snapshot,
        "tracking_number": shipment.tracking_number if shipment else None,
        "carrier_tracking_number": shipment.carrier_tracking_number if shipment else None,
        "carrier_barcode": shipment.carrier_barcode if shipment else None,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "parties": [
            {
                "role": p.role,
                "full_name": p.full_name,
                "phone": p.phone,
                "city": p.city,
                "address_line1": p.address_line1,
            }
            for p in order.parties
        ],
        "packages": [
            {
                "quantity": p.quantity,
                "weight_kg": float(p.weight_kg),
                "description": p.description,
            }
            for p in order.packages
        ],
        "cancellation": cancellation,
        "refund_status": refund_status,
        "cancellation_request": cancellation_request,
        "orphan_waybill_number": order.orphan_waybill_number,
    }


@router.get("/{order_id}/tracking")
def get_order_tracking_admin(
    order_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    """История трекинга для админа/оператора (без проверки owner)."""
    order = db.get(OrderDraft, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    events = _tracking_repo.list_events(db, order_draft_id=order_id)
    return {
        "order_draft_id": order_id,
        "carrier_code": order.carrier_code_snapshot,
        "events": [
            {
                "id": e.id,
                "status": e.status,
                "description": e.description,
                "location": e.location,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in events
        ],
    }


@router.patch("/{order_id}/status")
@limiter.limit("60/minute")
def update_order_status(
    request: Request,
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_or_operator),
) -> dict:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            422,
            f"Недопустимый статус. Допустимые: {sorted(VALID_STATUSES)}",
        )
    order = db.get(OrderDraft, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    old_status = order.status
    if not can_transition(old_status, payload.status):
        logger.warning(
            "admin status override: order %s transition %s → %s not in state machine",
            order_id, old_status, payload.status,
        )
    order.status = payload.status
    # When the order is moved into 'cancelled' from any other state, offset
    # the recorded commission with a storno row so admin totals stay honest.
    # reverse_for_order is idempotent — if the refund flow already reversed
    # it, this is a no-op.
    if payload.status == "cancelled" and old_status != "cancelled":
        _commissions_svc.reverse_for_order(
            db, order.id, reason="admin status change → cancelled"
        )
    db.add(OrderStatusHistory(
        order_id=order.id,
        old_status=old_status,
        new_status=payload.status,
        changed_by_user_id=admin.id,
        source="admin",
        comment="Manual status override by admin",
    ))
    _tracking_repo.add_event(
        db,
        order_draft_id=order.id,
        status=payload.status,
        description=f"Статус обновлён администратором: {payload.status}",
    )
    _notifications_svc.notify_order_status(
        db,
        user_id=order.user_id,
        order_id=order.id,
        status=payload.status,
    )
    _audit_svc.log(
        db,
        actor=admin,
        action="order.status_change",
        resource_type="order",
        resource_id=order.id,
        old_value={"status": old_status},
        new_value={"status": payload.status},
    )
    db.commit()
    return {"id": order.id, "status": order.status}


@router.post("/{draft_id}/retry-dispatch")
def retry_dispatch(
    draft_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_or_operator),
) -> dict:
    order = db.get(OrderDraft, draft_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if order.status not in (
        "dispatch_failed", "pending_manual", "pending_manual_dispatch", "dispatch_queued"
    ):
        raise HTTPException(
            400,
            f"Повтор отправки невозможен для заказа в статусе '{order.status}'",
        )

    tracking_number = _dispatch_svc.retry_for_order(db, order, admin_id=admin.id)

    _audit_svc.log(
        db,
        actor=admin,
        action="order.retry_dispatch",
        resource_type="order",
        resource_id=order.id,
        new_value={"tracking_number": tracking_number, "status": order.status},
    )
    db.commit()
    return {"ok": True, "tracking_number": tracking_number}


@router.post("/{draft_id}/retry-pickup")
def retry_azimuth_pickup(
    draft_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_or_operator),
) -> dict:
    """Retry ONLY the Azimuth /order-courier step for an order.

    Used when create_invoice succeeded but schedule_pickup failed — retrying
    the whole dispatch would create a duplicate waybill, so we expose a
    scoped retry that only touches the pickup call. Idempotent: refuses if
    pickup_scheduled_azimuth_id is already set.
    """
    order = db.get(OrderDraft, draft_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if (order.carrier_code_snapshot or "").lower() != "azimuth":
        raise HTTPException(400, "Retry pickup доступен только для Azimuth-заказов")
    if not order.pickup_requested:
        raise HTTPException(400, "Клиент не запрашивал вызов курьера для этого заказа")
    if order.pickup_scheduled_azimuth_id:
        raise HTTPException(
            409,
            "Курьер уже вызван по этому заказу (idempotency lock — "
            "pickup_scheduled_azimuth_id уже установлен).",
        )

    _dispatch_svc._schedule_azimuth_pickup(db, order)
    db.commit()

    _audit_svc.log(
        db,
        actor=admin,
        action="order.retry_pickup",
        resource_type="order",
        resource_id=order.id,
        new_value={
            "pickup_scheduled": bool(order.pickup_scheduled_azimuth_id),
            "pickup_error": order.pickup_error,
        },
    )
    db.commit()
    return {
        "ok": bool(order.pickup_scheduled_azimuth_id),
        "pickup_scheduled_azimuth_id": order.pickup_scheduled_azimuth_id,
        "pickup_error": order.pickup_error,
    }


@router.post("/{order_id}/refresh-waybill")
def refresh_waybill(
    order_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    from app.core.carrier_gateway_client import get_gateway_client
    from app.core.redis import get_redis
    from app.core.storage import get_storage
    from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
    from app.modules.documents.models import Document, DocumentType

    order = db.get(OrderDraft, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")

    shipment = _shipments_repo.get_by_order_id(db, order_id)
    if not shipment or not shipment.carrier_tracking_number:
        raise HTTPException(400, "У заказа нет трекинг-номера перевозчика")

    carrier_code = order.carrier_code_snapshot
    creds_record = CarrierAPICredentialsRepository().get_by_carrier_code(db, carrier_code)
    if not creds_record or not creds_record.is_active:
        raise HTTPException(400, f"Нет активных API-credentials для перевозчика '{carrier_code}'")

    api_creds = {
        "api_url": creds_record.api_url,
        "api_token": creds_record.api_token,
        **(creds_record.extra_config or {}),
    }

    try:
        pdf_bytes = get_gateway_client().get_invoice_pdf(
            carrier_code, shipment.carrier_tracking_number, api_creds
        )
    except Exception as exc:
        raise HTTPException(502, f"Не удалось получить накладную от перевозчика: {exc}") from exc

    storage = get_storage()
    stale_docs = db.scalars(
        select(Document).where(
            Document.order_id == order_id,
            Document.document_type == DocumentType.LABEL,
        )
    ).all()
    for doc in stale_docs:
        try:
            storage.delete_file(doc.file_url)
        except Exception as exc:
            logger.warning(
                "Failed to delete stale label from storage: %s (%s)",
                doc.file_url, exc,
            )
        db.delete(doc)

    get_redis().delete(f"pdf:label:{order_id}")

    filename = f"waybill_{shipment.carrier_tracking_number}.pdf"
    uploaded = storage.upload_file(
        file_data=pdf_bytes,
        original_name=filename,
        mime_type="application/pdf",
        folder=f"waybills/{order_id}",
    )
    db.add(Document(
        order_id=order_id,
        document_type=DocumentType.LABEL,
        file_url=uploaded.object_name,
        file_name=filename,
        mime_type="application/pdf",
    ))

    _audit_svc.log(
        db,
        actor=admin,
        action="order.refresh_waybill",
        resource_type="order",
        resource_id=order_id,
        new_value={"carrier_tracking_number": shipment.carrier_tracking_number},
    )
    db.commit()

    logger.info("Admin refreshed waybill: order_id=%s carrier=%s size=%d", order_id, carrier_code, len(pdf_bytes))
    return {"ok": True, "waybill_pdf_size": len(pdf_bytes)}


@router.post("/{draft_id}/mark-dispatched")
def mark_dispatched(
    draft_id: int,
    payload: MarkDispatchedPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_or_operator),
) -> dict:
    order = db.get(OrderDraft, draft_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if not can_transition(order.status, "sent_to_carrier"):
        raise HTTPException(
            400,
            f"Cannot mark order as dispatched from status '{order.status}'",
        )
    shipment = _shipments_repo.get_by_order_id(db, order.id)
    if shipment:
        shipment.carrier_tracking_number = payload.tracking_number
        shipment.status = "sent_to_carrier"
    old_status = order.status
    order.status = "sent_to_carrier"
    order.dispatch_error = None
    db.add(OrderStatusHistory(
        order_id=order.id,
        old_status=old_status,
        new_status="sent_to_carrier",
        changed_by_user_id=admin.id,
        source="admin",
        comment="Manually marked as dispatched",
    ))
    _tracking_repo.add_event(
        db,
        order_draft_id=order.id,
        status="sent_to_carrier",
        description="Передан перевозчику вручную",
    )
    _audit_svc.log(
        db,
        actor=admin,
        action="order.mark_dispatched",
        resource_type="order",
        resource_id=order.id,
        new_value={"tracking_number": payload.tracking_number, "status": "sent_to_carrier"},
    )
    db.commit()
    return {
        "id": order.id,
        "status": order.status,
        "carrier_tracking_number": payload.tracking_number,
    }


@router.post("/{order_id}/orphan-waybill/resolve")
def resolve_orphan_waybill(
    order_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_or_operator),
) -> dict:
    """Staff confirms the leftover waybill (after a failed reschedule cancel)
    was cancelled with the carrier by hand — clears the warning."""
    order = db.get(OrderDraft, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    old_value = order.orphan_waybill_number
    order.orphan_waybill_number = None
    _audit_svc.log(
        db,
        actor=admin,
        action="order.orphan_waybill_resolved",
        resource_type="order",
        resource_id=order.id,
        old_value={"orphan_waybill_number": old_value},
        new_value={"orphan_waybill_number": None},
    )
    db.commit()
    return {"id": order.id, "orphan_waybill_number": None}
