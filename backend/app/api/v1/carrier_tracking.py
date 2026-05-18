from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.carriers.webhook_config import CarrierWebhookRepository
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.status_mapper import map_carrier_status

logger = logging.getLogger(__name__)
router = APIRouter(tags=["carrier-tracking"])

_webhook_repo = CarrierWebhookRepository()
_tracking_repo = TrackingRepository()
_notifications_svc = NotificationsService()


@router.post(
    "/carriers/{carrier_code}/tracking-webhook",
    status_code=200,
    include_in_schema=False,
)
async def carrier_tracking_webhook(
    carrier_code: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    raw_body = await request.body()

    cfg = _webhook_repo.get_by_carrier_code(db, carrier_code)
    if cfg and cfg.webhook_secret:
        expected = hmac.new(
            cfg.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        received = request.headers.get("X-Carrier-Signature", "")
        if not hmac.compare_digest(expected, received):
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=400, detail="Invalid JSON") from err

    novex_order_id = body.get("novex_order_id")
    raw_status = body.get("status", "")
    location = body.get("location")
    description = body.get("description")

    if not novex_order_id:
        return {"ok": True}

    order = db.scalar(select(OrderDraft).where(OrderDraft.id == int(novex_order_id)))
    if not order:
        logger.warning("carrier tracking webhook: order %s not found", novex_order_id)
        return {"ok": True}

    novex_status = map_carrier_status(raw_status)

    _tracking_repo.add_event(
        db,
        order_draft_id=order.id,
        status=novex_status,
        carrier_status=raw_status,
        location=location,
        description=description,
    )

    if novex_status in ("delivered", "returned"):
        order.status = novex_status

    _notifications_svc.notify_order_status(
        db,
        user_id=order.user_id,
        order_id=order.id,
        status=novex_status,
    )

    db.commit()
    return {"ok": True}
