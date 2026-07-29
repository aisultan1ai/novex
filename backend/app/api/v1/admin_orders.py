from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common.status_machine import can_transition
from app.core.db import get_db
from app.core.dependencies import require_admin, require_admin_or_operator
from app.core.limiter import limiter
from app.modules.audit.service import AuditService
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


@router.get("")
@limiter.limit("120/minute")
def list_all_orders(
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    barcode: str | None = Query(default=None, description="Substring match on carrier barcode / tracking numbers"),
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    from app.modules.shipments.models import Shipment as _Shipment

    stmt = select(OrderDraft).order_by(OrderDraft.created_at.desc())
    if status:
        stmt = stmt.where(OrderDraft.status == status)
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
        }
        for o in orders
    ]

    pages = math.ceil(total / size) if total > 0 else 1
    logger.debug("admin list_all_orders: page=%d size=%d total=%d", page, size, total)
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


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
        except Exception:
            pass
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
