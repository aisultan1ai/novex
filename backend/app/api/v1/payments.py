from __future__ import annotations

import json
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.core.exceptions import NotFoundError, ValidationError
from app.core.limiter import limiter
from app.core.storage import get_storage, validate_upload
from app.modules.orders.repository import OrdersRepository
from app.modules.payments.payment_service import PaymentService
from app.modules.payments.providers.manual_bank_transfer import ManualBankTransferProvider
from app.modules.payments.transaction_models import TxStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

order_repo = OrdersRepository()
payment_svc = PaymentService()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class BankTransferDetails(BaseModel):
    recipient_name: str
    bank_name: str
    iban: str
    bin: str
    knp: str
    purpose: str
    amount: str
    currency: str


class InitiateBankTransferResponse(BaseModel):
    payment_id: int
    order_reference: str
    status: str
    bank_details: BankTransferDetails


class PaymentStatusResponse(BaseModel):
    payment_id: int
    order_id: int
    status: str
    payment_reference: str | None
    amount: float
    currency: str


# ─── Customer: initiate bank transfer ─────────────────────────────────────────

@router.post(
    "/orders/{draft_id}/initiate-bank-transfer",
    response_model=InitiateBankTransferResponse,
    summary="Инициировать оплату по банковским реквизитам",
)
@limiter.limit("10/minute")
def initiate_bank_transfer(
    request: Request,
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> InitiateBankTransferResponse:
    order = order_repo.get_order_draft_by_id(db, draft_id)
    if not order or order.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status not in ("ready_for_checkout", "awaiting_payment", "payment_rejected"):
        raise HTTPException(status_code=400, detail="Заказ не готов к оплате")

    tx = payment_svc.initiate_bank_transfer(db, order=order, user_id=current_user_id)

    from app.core.config import get_settings
    s = get_settings()
    provider = ManualBankTransferProvider(
        recipient_name=getattr(s, "bank_transfer_recipient_name", "ТОО Novex"),
        bank_name=getattr(s, "bank_transfer_bank_name", "Halyk Bank"),
        iban=getattr(s, "bank_transfer_iban", ""),
        bin_number=getattr(s, "bank_transfer_bin", ""),
        knp=getattr(s, "bank_transfer_knp", "710"),
    )
    details = provider.get_bank_details()

    return InitiateBankTransferResponse(
        payment_id=tx.id,
        order_reference=tx.payment_reference or f"NOVEX-{order.id:06d}",
        status=tx.status,
        bank_details=BankTransferDetails(
            recipient_name=details["recipient_name"],
            bank_name=details["bank_name"],
            iban=details["iban"],
            bin=details["bin"],
            knp=details["knp"],
            purpose=f"Оплата доставки по заказу {tx.payment_reference or f'NOVEX-{order.id:06d}'}",
            amount=str(tx.amount),
            currency=tx.currency,
        ),
    )


# ─── Customer: upload payment proof ───────────────────────────────────────────

@router.post(
    "/orders/{draft_id}/upload-proof",
    status_code=201,
    summary="Загрузить чек оплаты",
)
@limiter.limit("5/minute")
def upload_payment_proof(
    request: Request,
    draft_id: int,
    payment_id: int = Form(...),
    comment: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    order = order_repo.get_order_draft_by_id(db, draft_id)
    if not order or order.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    try:
        payment_svc.assert_payment_accepts_proof(
            db, payment_id=payment_id, order_id=draft_id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_data = file.file.read()
    mime_type = file.content_type or "application/octet-stream"

    try:
        validate_upload(file_data, file.filename or "file", mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    storage = get_storage()
    try:
        uploaded = storage.upload_file(
            file_data=file_data,
            original_name=file.filename or "proof",
            mime_type=mime_type,
            folder=f"payment_proofs/{draft_id}",
        )
    except Exception as exc:
        logger.error("File upload failed: %s", exc)
        raise HTTPException(status_code=500, detail="File upload failed")

    try:
        proof = payment_svc.submit_proof(
            db,
            payment_id=payment_id,
            order_id=draft_id,
            user_id=current_user_id,
            file_url=uploaded.file_url,
            file_name=uploaded.file_name,
            file_mime_type=uploaded.file_mime_type,
            file_size=uploaded.file_size,
            comment=comment,
        )
    except ValueError as exc:
        logger.error(
            "submit_proof failed after upload: payment_id=%s draft_id=%s file=%s error=%s",
            payment_id,
            draft_id,
            uploaded.file_name,
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "proof_id": proof.id,
        "status": proof.review_status,
        "message": "Чек загружен. Оплата отправлена на проверку оператором.",
    }


# ─── Customer: get payment status ─────────────────────────────────────────────

@router.get(
    "/orders/{draft_id}/payment-status",
    response_model=PaymentStatusResponse,
    summary="Статус оплаты заказа",
)
def get_payment_status(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PaymentStatusResponse:
    order = order_repo.get_order_draft_by_id(db, draft_id)
    if not order or order.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    tx = payment_svc.get_payment_for_order(db, order_id=draft_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    return PaymentStatusResponse(
        payment_id=tx.id,
        order_id=tx.order_id,
        status=tx.status,
        payment_reference=tx.payment_reference,
        amount=float(tx.amount),
        currency=tx.currency,
    )


# ─── Kaspi webhook (kept for future, disabled in production until onboarding) ─

@router.post(
    "/kaspi/webhook",
    status_code=200,
    include_in_schema=False,
)
async def kaspi_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    from app.core.config import get_settings
    settings = get_settings()

    if settings.is_production and not settings.kaspi_merchant_id:
        raise HTTPException(status_code=403, detail="Kaspi integration is not active")

    raw_body = await request.body()

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    from app.modules.payments.kaspi_service import KaspiPayService
    kaspi = KaspiPayService()

    signature = request.headers.get("X-Kaspi-Signature", "")
    if settings.kaspi_webhook_secret and not kaspi.verify_webhook(raw_body, signature):
        logger.warning("Kaspi webhook: invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    order_id_str, status = kaspi.parse_webhook(body)
    if not order_id_str or not status:
        return {"ok": True}

    # Idempotency via provider_webhook_events
    import hashlib
    event_id = body.get("PaymentId") or hashlib.sha256(raw_body).hexdigest()
    from sqlalchemy import text as _text
    existing = db.execute(
        _text(
            "SELECT id FROM provider_webhook_events "
            "WHERE provider = 'kaspi' AND external_event_id = :eid LIMIT 1"
        ),
        {"eid": event_id},
    ).fetchone()
    if existing:
        return {"ok": True, "duplicate": True}

    db.execute(
        _text(
            "INSERT INTO provider_webhook_events "
            "(provider, external_event_id, order_id, raw_payload, status, created_at) "
            "VALUES ('kaspi', :eid, :oid, :payload, 'received', NOW())"
        ),
        {
            "eid": event_id,
            "oid": int(order_id_str) if order_id_str else None,
            "payload": json.dumps(body),
        },
    )

    from app.modules.orders.repository import OrdersRepository
    order = OrdersRepository().get_order_draft_by_id(db, int(order_id_str))
    if not order:
        db.commit()
        return {"ok": True}

    # Validate amount matches
    amount_raw = body.get("Amount") or body.get("amount")
    if amount_raw is not None:
        paid_amount = Decimal(str(amount_raw)) / 100
        order_amount = Decimal(str(order.price_snapshot))
        if abs(paid_amount - order_amount) > Decimal("1.00"):
            logger.warning(
                "Kaspi webhook: amount mismatch order=%s paid=%s expected=%s",
                order_id_str, paid_amount, order_amount,
            )
            db.execute(
                _text(
                    "UPDATE provider_webhook_events SET status = 'failed' "
                    "WHERE provider = 'kaspi' AND external_event_id = :eid"
                ),
                {"eid": event_id},
            )
            db.commit()
            return {"ok": True}

    if status == "paid":
        tx = payment_svc.get_payment_for_order(db, order_id=order.id)
        if tx:
            payment_svc.admin_approve(db, payment_id=tx.id, admin_id=0)
            logger.info("Kaspi webhook: order %s paid, tx_id=%s", order_id_str, tx.id)
        else:
            logger.warning("Kaspi webhook: no payment transaction for order %s", order_id_str)
    elif status == "cancelled":
        old_status = order.status
        order.status = "cancelled"
        from app.modules.dispatch.models import OrderStatusHistory
        db.add(OrderStatusHistory(
            order_id=order.id,
            old_status=old_status,
            new_status="cancelled",
            source="payment_webhook",
            comment="Cancelled via Kaspi webhook",
        ))

    db.execute(
        _text(
            "UPDATE provider_webhook_events SET status = 'processed', processed_at = NOW() "
            "WHERE provider = 'kaspi' AND external_event_id = :eid"
        ),
        {"eid": event_id},
    )
    db.commit()
    return {"ok": True}
