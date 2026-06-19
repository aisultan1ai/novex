from __future__ import annotations

import json
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.status_machine import can_transition
from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
from app.modules.carriers.integration_log import IntegrationLogRepository
from app.modules.carriers.polling.registry import get_adapter
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.notifications.service import NotificationsService
from app.modules.shipments.models import Shipment
from app.modules.tracking.models import TrackingEvent
from app.modules.tracking.repository import TrackingRepository

logger = logging.getLogger(__name__)

_tracking_repo = TrackingRepository()
_notifications_svc = NotificationsService()
_creds_repo = CarrierAPICredentialsRepository()
_integration_log = IntegrationLogRepository()

_ACTIVE_STATUSES = {"sent_to_carrier", "dispatched", "picked_up", "in_transit", "out_for_delivery", "customs_hold", "delivery_failed"}


def poll_all_active_shipments(db: Session) -> None:
    from app.modules.orders.models import OrderDraft

    shipments = db.scalars(
        select(Shipment)
        .join(OrderDraft, OrderDraft.id == Shipment.order_draft_id)
        .where(OrderDraft.status.in_(_ACTIVE_STATUSES))
        .limit(200)
    ).all()

    for shipment in shipments:
        if not shipment.carrier_tracking_number:
            continue

        order = db.get(OrderDraft, shipment.order_draft_id)
        if order is None:
            continue

        adapter = get_adapter(order.carrier_code_snapshot)
        if adapter is None:
            continue

        db_creds = _creds_repo.get_by_carrier_code(db, order.carrier_code_snapshot)
        creds: dict = {}
        if db_creds and db_creds.is_active:
            creds = {"api_url": db_creds.api_url, **(db_creds.extra_config or {})}

        t0 = time.monotonic()
        try:
            events = adapter.fetch_status(shipment.carrier_tracking_number, creds)
            duration_ms = int((time.monotonic() - t0) * 1000)
            _integration_log.create(
                db,
                carrier_code=order.carrier_code_snapshot,
                direction="outbound",
                event_type="polling",
                order_id=order.id,
                payload=json.dumps({"tracking_number": shipment.carrier_tracking_number}),
                response=json.dumps({"events_count": len(events)}),
                duration_ms=duration_ms,
                status="success",
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            _integration_log.create(
                db,
                carrier_code=order.carrier_code_snapshot,
                direction="outbound",
                event_type="polling",
                order_id=order.id,
                payload=json.dumps({"tracking_number": shipment.carrier_tracking_number}),
                duration_ms=duration_ms,
                status="error",
                error_message=str(exc),
            )
            logger.warning(
                "polling failed for shipment %s (%s): %s",
                shipment.id,
                shipment.carrier_tracking_number,
                exc,
            )
            continue

        for ev in events:
            duplicate = db.scalar(
                select(TrackingEvent).where(
                    TrackingEvent.order_draft_id == order.id,
                    TrackingEvent.carrier_status == ev.carrier_status,
                    TrackingEvent.occurred_at == ev.occurred_at,
                )
            )
            if duplicate:
                continue

            _tracking_repo.add_event(
                db,
                order_draft_id=order.id,
                status=ev.status,
                carrier_status=ev.carrier_status,
                location=ev.location,
                description=ev.description,
                occurred_at=ev.occurred_at,
            )

            if can_transition(order.status, ev.status):
                old_status = order.status
                order.status = ev.status
                db.add(OrderStatusHistory(
                    order_id=order.id,
                    old_status=old_status,
                    new_status=ev.status,
                    source="polling",
                    comment=f"Carrier status: {ev.carrier_status}",
                ))
            elif ev.status != order.status:
                logger.warning(
                    "polling: invalid transition order_id=%s %s → %s (carrier=%s)",
                    order.id, order.status, ev.status, ev.carrier_status,
                )

            _notifications_svc.notify_order_status(
                db,
                user_id=order.user_id,
                order_id=order.id,
                status=ev.status,
            )

        try:
            db.commit()
        except Exception as exc:
            logger.error(
                "commit failed after polling shipment %s: %s", shipment.id, exc
            )
            db.rollback()
