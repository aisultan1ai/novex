from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.orders.repository import OrdersRepository
from app.modules.payments.kaspi_service import KaspiPayService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

kaspi = KaspiPayService()
order_repo = OrdersRepository()


class InitiatePaymentResponse(BaseModel):
    payment_url: str
    kaspi_payment_id: str


@router.post(
    "/orders/{draft_id}/kaspi",
    response_model=InitiatePaymentResponse,
    summary="Инициировать оплату через Kaspi Pay",
)
def initiate_kaspi_payment(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> InitiatePaymentResponse:
    order = order_repo.get_order_draft_by_id(db, draft_id)
    if not order or order.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status not in ("ready_for_checkout", "awaiting_payment"):
        raise HTTPException(status_code=400, detail="Заказ не готов к оплате")

    order.status = "awaiting_payment"
    db.commit()

    result = kaspi.create_payment(
        order_id=order.id,
        amount_kzt=float(order.price_snapshot),
        description=f"Доставка {order.from_city_snapshot} → {order.to_city_snapshot}",
    )
    return InitiatePaymentResponse(
        payment_url=result.payment_url,
        kaspi_payment_id=result.kaspi_payment_id,
    )


@router.post(
    "/kaspi/webhook",
    status_code=200,
    summary="Webhook от Kaspi Pay (server-to-server)",
    include_in_schema=False,
)
async def kaspi_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("X-Kaspi-Signature", "")

    if not kaspi.verify_webhook(raw_body, signature):
        logger.warning("Kaspi webhook: неверная подпись")
        raise HTTPException(status_code=400, detail="Invalid signature")

    body = await request.json()
    order_id_str, status = kaspi.parse_webhook(body)

    if not order_id_str or not status:
        return {"ok": True}

    order = order_repo.get_order_draft_by_id(db, int(order_id_str))
    if not order:
        logger.warning("Kaspi webhook: заказ %s не найден", order_id_str)
        return {"ok": True}

    if status == "paid":
        order.status = "paid"
        logger.info("Заказ #%s оплачен через Kaspi", order_id_str)
    elif status == "cancelled":
        order.status = "cancelled"
        logger.info("Заказ #%s отменён через Kaspi", order_id_str)

    db.commit()
    return {"ok": True}
