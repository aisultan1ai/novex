from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.identity.models import CustomerProfile, Role, RoleCode, User
from app.modules.orders.models import OrderDraft

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ) or 0
    total_orders = db.scalar(select(func.count(OrderDraft.id))) or 0
    paid_orders = db.scalar(
        select(func.count(OrderDraft.id)).where(OrderDraft.status == "paid")
    ) or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
    }


# ── Users list ────────────────────────────────────────────────────────────────

@router.get("")
def list_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    stmt = (
        select(User)
        .options(joinedload(User.role), joinedload(User.customer_profile))
        .order_by(User.id.desc())
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(User.email.ilike(like) | User.full_name.ilike(like))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()

    page_user_ids = [u.id for u in users]
    order_counts_raw = db.execute(
        select(OrderDraft.user_id, func.count(OrderDraft.id).label("cnt"))
        .where(OrderDraft.user_id.in_(page_user_ids))
        .group_by(OrderDraft.user_id)
    ).all()
    order_counts = {row.user_id: row.cnt for row in order_counts_raw}

    items = [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "phone": u.phone,
            "is_active": u.is_active,
            "role": u.role.code.value if u.role else None,
            "customer_type": (
                u.customer_profile.customer_type.value if u.customer_profile else None
            ),
            "company_name": (
                u.customer_profile.company_name if u.customer_profile else None
            ),
            "order_count": order_counts.get(u.id, 0),
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]

    return {"items": items, "total": total, "page": page, "size": size}


# ── User detail ───────────────────────────────────────────────────────────────

@router.get("/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    user = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.customer_profile))
        .where(User.id == user_id)
    )
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    orders = db.scalars(
        select(OrderDraft)
        .where(OrderDraft.user_id == user_id)
        .order_by(OrderDraft.created_at.desc())
        .limit(50)
    ).all()

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "role": user.role.code.value if user.role else None,
        "customer_type": (
            user.customer_profile.customer_type.value if user.customer_profile else None
        ),
        "company_name": (
            user.customer_profile.company_name if user.customer_profile else None
        ),
        "billing_mode": (
            user.customer_profile.billing_mode.value if user.customer_profile else None
        ),
        "created_at": user.created_at.isoformat(),
        "orders": [
            {
                "id": o.id,
                "status": o.status,
                "from_city": o.from_city_snapshot,
                "to_city": o.to_city_snapshot,
                "carrier_name": o.carrier_name_snapshot,
                "tariff_name": o.tariff_name_snapshot,
                "price": float(o.price_snapshot),
                "currency": o.currency_snapshot,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    }


# ── User update ───────────────────────────────────────────────────────────────

@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    return {"id": user.id, "is_active": user.is_active}
