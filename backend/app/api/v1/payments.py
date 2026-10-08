from __future__ import annotations

import json
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.status_machine import can_transition
from app.core.db import get_db
from app.core.dependencies import get_current_user_id, require_verified_email
from app.core.exceptions import NotFoundError, ValidationError
from app.core.limiter import limiter
from app.core.storage import MAX_FILE_SIZE, get_storage
from app.modules.commissions.service import CommissionsService
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.orders.repository import OrdersRepository
from app.modules.payments.payment_service import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

order_repo = OrdersRepository()
payment_svc = PaymentService()
_commissions_svc = CommissionsService()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class BankTransferDetails(BaseModel):
    recipient_name: str
    bank_name: str
    iban: str
    bin: str
    knp: str
    bik: str = ""
    kbe: str = ""
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
    _verified = Depends(require_verified_email),
    db: Session = Depends(get_db),
) -> InitiateBankTransferResponse:
    order = order_repo.get_order_draft_by_id(db, draft_id)
    if not order or order.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status not in ("ready_for_checkout", "awaiting_payment", "payment_rejected"):
        raise HTTPException(status_code=400, detail="Заказ не готов к оплате")

    tx = payment_svc.initiate_bank_transfer(db, order=order, user_id=current_user_id)
    details = payment_svc.get_bank_details(db)

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
            bik=details.get("bik", ""),
            kbe=details.get("kbe", ""),
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
async def upload_payment_proof(
    request: Request,
    draft_id: int,
    payment_id: int = Form(...),
    comment: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user_id),
    _verified = Depends(require_verified_email),
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

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой (максимум {MAX_FILE_SIZE // (1024 * 1024)} МБ)")  # noqa: E501
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой (максимум {MAX_FILE_SIZE // (1024 * 1024)} МБ)")  # noqa: E501
    mime_type = file.content_type or "application/octet-stream"

    storage = get_storage()
    try:
        uploaded = storage.upload_file(
            file_data=file_data,
            original_name=file.filename or "proof",
            mime_type=mime_type,
            folder=f"payment_proofs/{draft_id}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        logger.error("Storage unavailable: %s", exc)
        raise HTTPException(status_code=500, detail="Хранилище файлов временно недоступно. Попробуйте позже.")
    except Exception as exc:
        logger.error("File upload failed: %s", exc)
        raise HTTPException(status_code=500, detail="Не удалось загрузить файл. Попробуйте ещё раз.")

    try:
        proof = payment_svc.submit_proof(
            db,
            payment_id=payment_id,
            order_id=draft_id,
            user_id=current_user_id,
            file_url=uploaded.object_name,
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

    from app.modules.notifications.staff import notify_staff
    notify_staff(db, event="payment_proof", order_id=draft_id)

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

def _build_kaspi_provider():
    from app.core.config import get_settings
    from app.modules.payments.providers.kaspi import KaspiProvider
    s = get_settings()
    return KaspiProvider(
        merchant_id=s.kaspi_merchant_id,
        api_key=s.kaspi_api_key,
        api_url=s.kaspi_api_url,
        webhook_secret=s.kaspi_webhook_secret,
        frontend_url=s.frontend_url,
        backend_url=s.backend_url,
    )


@router.post(
    "/kaspi/webhook",
    status_code=200,
    include_in_schema=False,
)
async def kaspi_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import text as _text

    from app.core.config import get_settings
    settings = get_settings()

    if settings.is_production and not settings.kaspi_merchant_id:
        raise HTTPException(status_code=403, detail="Kaspi integration is not active")

    raw_body = await request.body()
    headers = dict(request.headers)
    kaspi = _build_kaspi_provider()

    if settings.kaspi_webhook_secret and not kaspi.verify_webhook(raw_body, headers):
        logger.warning("Kaspi webhook: invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = kaspi.parse_webhook(raw_body, headers)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Kaspi webhook: parse failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid payload")

    if not event.order_id or not event.status:
        return {"ok": True}

    # Idempotency via provider_webhook_events
    existing = db.execute(
        _text(
            "SELECT id FROM provider_webhook_events "
            "WHERE provider = 'kaspi' AND external_event_id = :eid LIMIT 1"
        ),
        {"eid": event.external_event_id},
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
            "eid": event.external_event_id,
            "oid": int(event.order_id),
            "payload": json.dumps(event.raw),
        },
    )

    from app.modules.orders.repository import OrdersRepository
    order = OrdersRepository().get_order_draft_by_id(db, int(event.order_id))
    if not order:
        db.commit()
        return {"ok": True}

    # Validate amount matches
    if event.amount is not None:
        order_amount = Decimal(str(order.price_snapshot))
        if abs(event.amount - order_amount) > Decimal("1.00"):
            logger.warning(
                "Kaspi webhook: amount mismatch order=%s paid=%s expected=%s",
                event.order_id, event.amount, order_amount,
            )
            db.execute(
                _text(
                    "UPDATE provider_webhook_events SET status = 'failed' "
                    "WHERE provider = 'kaspi' AND external_event_id = :eid"
                ),
                {"eid": event.external_event_id},
            )
            db.commit()
            return {"ok": True}

    if event.status == "paid":
        tx = payment_svc.get_payment_for_order(db, order_id=order.id)
        if tx:
            try:
                payment_svc.system_confirm_payment(
                    db, payment_id=tx.id, source="kaspi_webhook"
                )
                logger.info("Kaspi webhook: order %s paid, tx_id=%s", event.order_id, tx.id)
            except Exception as exc:
                logger.error(
                    "Kaspi webhook: system_confirm_payment failed order=%s tx=%s: %s",
                    event.order_id, tx.id, exc,
                )
                raise HTTPException(status_code=500, detail="Payment confirmation failed")
        else:
            logger.warning("Kaspi webhook: no payment transaction for order %s", event.order_id)
    elif event.status == "cancelled":
        if can_transition(order.status, "cancelled"):
            old_status = order.status
            order.status = "cancelled"
            db.add(OrderStatusHistory(
                order_id=order.id,
                old_status=old_status,
                new_status="cancelled",
                source="kaspi_webhook",
                comment="Cancelled via Kaspi webhook",
            ))
            _commissions_svc.reverse_for_order(
                db, order.id, reason="kaspi webhook: cancelled"
            )
        else:
            logger.warning(
                "Kaspi webhook: cannot cancel order %s from status '%s'",
                order.id, order.status,
            )

    db.execute(
        _text(
            "UPDATE provider_webhook_events SET status = 'processed', processed_at = NOW() "
            "WHERE provider = 'kaspi' AND external_event_id = :eid"
        ),
        {"eid": event.external_event_id},
    )
    db.commit()
    return {"ok": True}
