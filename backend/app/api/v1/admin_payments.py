from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.audit.service import AuditService
from app.modules.identity.models import User
from app.modules.payments.payment_service import PaymentService
from app.modules.payments.transaction_models import PaymentTransaction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/payments", tags=["admin-payments"])

_payment_svc = PaymentService()
_audit_svc = AuditService()


class PaymentListItem(BaseModel):
    id: int
    order_id: int
    provider: str
    method: str
    status: str
    amount: float
    currency: str
    payment_reference: str | None
    created_at: str

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentListItem]
    total: int


class RejectPaymentRequest(BaseModel):
    reject_reason: str = Field(min_length=1, max_length=500)


def _to_item(tx: PaymentTransaction) -> PaymentListItem:
    return PaymentListItem(
        id=tx.id,
        order_id=tx.order_id,
        provider=tx.provider,
        method=tx.method,
        status=tx.status,
        amount=float(tx.amount),
        currency=tx.currency,
        payment_reference=tx.payment_reference,
        created_at=tx.created_at.isoformat(),
    )


@router.get("", response_model=PaymentListResponse, summary="Список оплат")
def list_payments(
    status: str | None = Query(default=None),
    order_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PaymentListResponse:
    offset = (page - 1) * size
    items, total = _payment_svc.list_for_admin(
        db, status=status, order_id=order_id, offset=offset, limit=size
    )
    return PaymentListResponse(
        items=[_to_item(tx) for tx in items],
        total=total,
    )


@router.get("/{payment_id}", summary="Детали оплаты")
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    from sqlalchemy import select
    from app.modules.payments.transaction_models import PaymentProof, PaymentStatusHistory

    tx = db.get(PaymentTransaction, payment_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    proofs = db.scalars(
        select(PaymentProof)
        .where(PaymentProof.payment_id == payment_id)
        .order_by(PaymentProof.created_at.desc())
    ).all()

    history = db.scalars(
        select(PaymentStatusHistory)
        .where(PaymentStatusHistory.payment_id == payment_id)
        .order_by(PaymentStatusHistory.created_at.asc())
    ).all()

    return {
        "payment": _to_item(tx).model_dump(),
        "proofs": [
            {
                "id": p.id,
                "file_url": p.file_url,
                "file_name": p.file_name,
                "file_mime_type": p.file_mime_type,
                "file_size": p.file_size,
                "comment": p.comment,
                "review_status": p.review_status,
                "reject_reason": p.reject_reason,
                "created_at": p.created_at.isoformat(),
                "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            }
            for p in proofs
        ],
        "history": [
            {
                "old_status": h.old_status,
                "new_status": h.new_status,
                "comment": h.comment,
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ],
    }


@router.post("/{payment_id}/approve", summary="Подтвердить оплату")
def approve_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    try:
        tx = _payment_svc.admin_approve(db, payment_id=payment_id, admin_id=admin.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _audit_svc.log(
        db,
        actor=admin,
        action="payment.approve",
        resource_type="payment",
        resource_id=tx.id,
        new_value={"order_id": tx.order_id, "status": tx.status},
    )
    db.commit()
    return {
        "payment_id": tx.id,
        "status": tx.status,
        "message": "Оплата подтверждена. Заказ передан в очередь на отправку.",
    }


@router.post("/{payment_id}/reject", summary="Отклонить оплату")
def reject_payment(
    payment_id: int,
    payload: RejectPaymentRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    try:
        tx = _payment_svc.admin_reject(
            db,
            payment_id=payment_id,
            admin_id=admin.id,
            reject_reason=payload.reject_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    _audit_svc.log(
        db,
        actor=admin,
        action="payment.reject",
        resource_type="payment",
        resource_id=tx.id,
        new_value={"order_id": tx.order_id, "status": tx.status, "reason": payload.reject_reason},
    )
    db.commit()
    return {
        "payment_id": tx.id,
        "status": tx.status,
        "message": "Оплата отклонена. Клиент уведомлён.",
    }
