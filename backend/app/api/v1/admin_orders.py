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
    db: Session = Depends(get_db),
    _=Depends(require_admin_or_operator),
) -> dict:
    stmt = select(OrderDraft).order_by(OrderDraft.created_at.desc())
    if status:
        stmt = stmt.where(OrderDraft.status == status)
    if user_id:
        stmt = stmt.where(OrderDraft.user_id == user_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    orders = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()

    user_ids = {o.user_id for o in orders}
    users_map: dict[int, User] = {}
    if user_ids:
        users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u for u in users}

    from app.modules.shipments.models import Shipment as _Shipment
    order_ids = [o.id for o in orders]
    shipments_map: dict[int, str] = {}
    if order_ids:
        shps = db.scalars(select(_Shipment).where(_Shipment.order_draft_id.in_(order_ids))).all()
        shipments_map = {s.order_draft_id: s.tracking_number for s in shps}

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
            "tariff_name": o.tariff_name_snapshot,
            "price": float(o.price_snapshot),
            "currency": o.currency_snapshot,
            "created_at": o.created_at.isoformat(),
            "tracking_number": shipments_map.get(o.id),
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
        "currency": order.currency_snapshot,
        "eta_days_min": order.eta_days_min_snapshot,
        "eta_days_max": order.eta_days_max_snapshot,
        "shipment_type": order.shipment_type_snapshot,
        "tracking_number": shipment.tracking_number if shipment else None,
        "carrier_tracking_number": shipment.carrier_tracking_number if shipment else None,
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
