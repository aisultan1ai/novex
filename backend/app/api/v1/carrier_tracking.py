from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.status_machine import can_transition
from app.core.config import get_settings
from app.core.db import get_db
from app.modules.carriers.integration_log import IntegrationLogRepository
from app.modules.carriers.webhook_config import CarrierWebhookRepository
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.notifications.service import NotificationsService
from app.modules.orders.models import OrderDraft
from app.modules.tracking.models import TrackingWebhookEvent
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.status_mapper import map_carrier_status

logger = logging.getLogger(__name__)
router = APIRouter(tags=["carrier-tracking"])

_webhook_repo = CarrierWebhookRepository()
_tracking_repo = TrackingRepository()
_integration_log = IntegrationLogRepository()
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
        # Verify timestamp to prevent replay attacks — header is mandatory when secret is configured
        ts_header = request.headers.get("X-Novex-Timestamp", "")
        if not ts_header:
            raise HTTPException(status_code=400, detail="Missing X-Novex-Timestamp header")
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
    existing = db.scalar(
        select(TrackingWebhookEvent).where(
            TrackingWebhookEvent.carrier_code == carrier_code,
            TrackingWebhookEvent.external_event_id == external_event_id,
        )
    )
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

    order_id_int: int | None = None
    if novex_order_id is not None:
        try:
            order_id_int = int(novex_order_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid novex_order_id: expected integer, got {novex_order_id!r}",
            )

    order: OrderDraft | None = None
    if order_id_int is not None:
        order = db.scalar(
            select(OrderDraft).where(OrderDraft.id == order_id_int)
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
    webhook_event = TrackingWebhookEvent(
        carrier_code=carrier_code,
        external_event_id=external_event_id,
        order_id=order_id_int,
        raw_payload=json.dumps(body),
        status="received",
    )
    db.add(webhook_event)
    db.flush()

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

        if novex_status and can_transition(order.status, novex_status):
            old_order_status = order.status
            order.status = novex_status
            db.add(OrderStatusHistory(
                order_id=order.id,
                old_status=old_order_status,
                new_status=novex_status,
                source="carrier_webhook",
                comment=f"Carrier status update: {raw_status}",
            ))
        elif novex_status and novex_status != order.status:
            logger.warning(
                "carrier_tracking: invalid transition order_id=%s %s → %s (carrier_status=%s)",
                order.id, order.status, novex_status, raw_status,
            )

        _notifications_svc.notify_order_status(
            db,
            user_id=order.user_id,
            order_id=order.id,
            status=novex_status,
        )

        # Mark event as processed
        from datetime import UTC, datetime
        webhook_event.status = "processed"
        webhook_event.processed_at = datetime.now(UTC).replace(tzinfo=None)

    # Log to carrier_integration_logs
    _integration_log.create(
        db,
        carrier_code=carrier_code,
        direction="inbound",
        event_type="tracking_webhook",
        order_id=order_id_int,
        payload=json.dumps(body),
        status="success",
    )

    db.commit()
    return {"ok": True}
