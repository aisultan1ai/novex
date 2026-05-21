from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
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

_REPLAY_WINDOW_SECONDS = 300


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "*" * len(secret)
    return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]


def _event_id_from_body(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


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
    settings = get_settings()
    raw_body = await request.body()

    cfg = _webhook_repo.get_by_carrier_code(db, carrier_code)
    if cfg is None:
        logger.warning("carrier tracking webhook: unknown carrier_code=%s", carrier_code)
        raise HTTPException(status_code=404, detail="Carrier not found")

    if not cfg.webhook_secret:
        if settings.is_production:
            logger.warning(
                "carrier tracking webhook: no secret configured for carrier=%s, rejecting in production",
                carrier_code,
            )
            raise HTTPException(status_code=403, detail="Webhook secret not configured")
        logger.warning(
            "carrier tracking webhook: no secret for carrier=%s, skipping HMAC in dev mode",
            carrier_code,
        )
    else:
        # Verify timestamp to prevent replay attacks
        ts_header = request.headers.get("X-Novex-Timestamp", "")
        if ts_header:
            try:
                ts = int(ts_header)
                if abs(time.time() - ts) > _REPLAY_WINDOW_SECONDS:
                    raise HTTPException(status_code=400, detail="Request timestamp expired")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid timestamp header")

        received = request.headers.get("X-Carrier-Signature", "")
        expected = hmac.new(
            cfg.webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, received):
            logger.warning(
                "carrier tracking webhook: invalid HMAC for carrier=%s", carrier_code
            )
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=400, detail="Invalid JSON") from err

    external_event_id = body.get("event_id") or _event_id_from_body(raw_body)

    # Idempotency: skip already-processed events
    from sqlalchemy import text as _text

    existing = db.execute(
        _text(
            "SELECT id FROM tracking_webhook_events "
            "WHERE carrier_code = :carrier_code AND external_event_id = :event_id "
            "LIMIT 1"
        ),
        {"carrier_code": carrier_code, "event_id": external_event_id},
    ).fetchone()
    if existing:
        logger.info(
            "carrier tracking webhook: duplicate event_id=%s carrier=%s, skipping",
            external_event_id,
            carrier_code,
        )
        return {"ok": True, "duplicate": True}

    novex_order_id = body.get("novex_order_id")
    raw_status = body.get("status", "")
    location = body.get("location")
    description = body.get("description")

    order: OrderDraft | None = None
    if novex_order_id:
        order = db.scalar(
            select(OrderDraft).where(OrderDraft.id == int(novex_order_id))
        )
        if not order:
            logger.warning(
                "carrier tracking webhook: order %s not found", novex_order_id
            )
        elif order.carrier_code_snapshot != carrier_code:
            logger.warning(
                "carrier tracking webhook: carrier_code mismatch order=%s "
                "url_carrier=%s order_carrier=%s",
                novex_order_id,
                carrier_code,
                order.carrier_code_snapshot,
            )
            raise HTTPException(status_code=400, detail="Carrier code mismatch")

    # Record the event before processing (idempotency row)
    db.execute(
        _text(
            "INSERT INTO tracking_webhook_events "
            "(carrier_code, external_event_id, order_id, raw_payload, status, created_at) "
            "VALUES (:carrier_code, :event_id, :order_id, :payload, 'received', NOW())"
        ),
        {
            "carrier_code": carrier_code,
            "event_id": external_event_id,
            "order_id": int(novex_order_id) if novex_order_id else None,
            "payload": json.dumps(body),
        },
    )

    if order and raw_status:
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

        # Mark event as processed
        db.execute(
            _text(
                "UPDATE tracking_webhook_events SET status = 'processed', processed_at = NOW() "
                "WHERE carrier_code = :carrier_code AND external_event_id = :event_id"
            ),
            {"carrier_code": carrier_code, "event_id": external_event_id},
        )

    db.commit()
    return {"ok": True}
