from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.identity.models import User
from app.modules.orders.models import OrderDraft

router = APIRouter(prefix="/admin/orders", tags=["admin:orders"])

VALID_STATUSES = {
    "draft", "shipment_details_completed", "ready_for_checkout",
    "awaiting_payment", "paid", "sent_to_carrier", "picked_up",
    "in_transit", "arrived", "delivered", "cancelled", "return",
}


class OrderStatusUpdate(BaseModel):
    status: str


@router.get("")
def list_all_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
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

    items = [
        {
            "id": o.id,
            "status": o.status,
            "user_id": o.user_id,
            "user_email": users_map[o.user_id].email if o.user_id in users_map else None,
            "user_name": users_map[o.user_id].full_name if o.user_id in users_map else None,
            "from_city": o.from_city_snapshot,
            "to_city": o.to_city_snapshot,
            "carrier_name": o.carrier_name_snapshot,
            "tariff_name": o.tariff_name_snapshot,
            "price": float(o.price_snapshot),
            "currency": o.currency_snapshot,
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]

    return {"items": items, "total": total, "page": page, "size": size}


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
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
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            422,
            f"Недопустимый статус. Допустимые: {sorted(VALID_STATUSES)}",
        )
    order = db.get(OrderDraft, order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    order.status = payload.status
    db.commit()
    return {"id": order.id, "status": order.status}
