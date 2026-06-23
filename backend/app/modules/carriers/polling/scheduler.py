from __future__ import annotations

import json
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.common.status_machine import can_transition
from app.core.carrier_gateway_client import (
    CarrierGatewayClient,
    GatewayTrackingEvent,
    get_gateway_client,
)
from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
from app.modules.carriers.integration_log import IntegrationLogRepository
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

_ACTIVE_STATUSES = {
    "sent_to_carrier", "dispatched", "picked_up", "in_transit",
    "out_for_delivery", "customs_hold", "delivery_failed",
}
_MAX_WORKERS = 10

# Only re-poll a shipment after this cooldown to avoid redundant carrier API calls.
_POLL_COOLDOWN_SECONDS = 100

# Module-level TTL cache for carrier credentials — avoids a DB query every 120s
# per carrier. Invalidates automatically after 5 minutes.
_creds_ttl: dict[str, tuple[dict, float]] = {}
_CREDS_TTL_SECS = 300


def _get_creds(db: Session, carrier_code: str) -> dict:
    """Return carrier creds from cache or DB. Cache TTL = 5 minutes."""
    entry = _creds_ttl.get(carrier_code)
    if entry and time.monotonic() - entry[1] < _CREDS_TTL_SECS:
        return entry[0]
    db_creds = _creds_repo.get_by_carrier_code(db, carrier_code)
    creds = (
        {"api_url": db_creds.api_url, **(db_creds.extra_config or {})}
        if db_creds and db_creds.is_active
        else {}
    )
    _creds_ttl[carrier_code] = (creds, time.monotonic())
    return creds


@dataclass
class _PollWork:
    shipment: Any
    order: Any
    creds: dict


@dataclass
class _PollResult:
    shipment: Any
    order: Any
    events: list[GatewayTrackingEvent]
    error: Exception | None
    duration_ms: int


def _fetch(work: _PollWork, gateway: CarrierGatewayClient) -> _PollResult:
    t0 = time.monotonic()
    try:
        events = gateway.fetch_tracking(
            work.order.carrier_code_snapshot,
            work.shipment.carrier_tracking_number,
            work.creds,
        )
        return _PollResult(
            shipment=work.shipment,
            order=work.order,
            events=events,
            error=None,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as exc:
        return _PollResult(
            shipment=work.shipment,
            order=work.order,
            events=[],
            error=exc,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )


def poll_all_active_shipments(db: Session) -> None:
    from app.modules.orders.models import OrderDraft

    cooldown_threshold = datetime.utcnow() - timedelta(seconds=_POLL_COOLDOWN_SECONDS)

    rows = db.execute(
        select(Shipment, OrderDraft)
        .join(OrderDraft, OrderDraft.id == Shipment.order_draft_id)
        .where(
            OrderDraft.status.in_(_ACTIVE_STATUSES),
            # Skip shipments polled recently — prevents hammering carrier APIs.
            or_(
                Shipment.last_polled_at.is_(None),
                Shipment.last_polled_at < cooldown_threshold,
            ),
        )
        .limit(200)
    ).all()

    work_items: list[_PollWork] = []

    for shipment, order in rows:
        if not shipment.carrier_tracking_number:
            continue
        work_items.append(_PollWork(
            shipment=shipment,
            order=order,
            creds=_get_creds(db, order.carrier_code_snapshot),
        ))

    if not work_items:
        return

    gateway = get_gateway_client()

    results: list[_PollResult] = []
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(work_items))) as pool:
        futures: dict[Future, _PollWork] = {
            pool.submit(_fetch, w, gateway): w for w in work_items
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    for result in results:
        shipment = result.shipment
        order = result.order

        # Mark as polled regardless of outcome — prevents retry storms on broken carriers.
        shipment.last_polled_at = datetime.utcnow()

        if result.error is not None:
            _integration_log.create(
                db,
                carrier_code=order.carrier_code_snapshot,
                direction="outbound",
                event_type="polling",
                order_id=order.id,
                payload=json.dumps({"tracking_number": shipment.carrier_tracking_number}),
                duration_ms=result.duration_ms,
                status="error",
                error_message=str(result.error),
            )
            logger.warning(
                "polling failed for shipment %s (%s): %s",
                shipment.id, shipment.carrier_tracking_number, result.error,
            )
            try:
                db.commit()
            except Exception as exc:
                logger.error("commit failed (error branch) shipment %s: %s", shipment.id, exc)
                db.rollback()
            continue

        _integration_log.create(
            db,
            carrier_code=order.carrier_code_snapshot,
            direction="outbound",
            event_type="polling",
            order_id=order.id,
            payload=json.dumps({"tracking_number": shipment.carrier_tracking_number}),
            response=json.dumps({"events_count": len(result.events)}),
            duration_ms=result.duration_ms,
            status="success",
        )

        for ev in result.events:
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
                _notifications_svc.notify_order_status(
                    db,
                    user_id=order.user_id,
                    order_id=order.id,
                    status=ev.status,
                )
            elif ev.status != order.status:
                logger.warning(
                    "polling: invalid transition order_id=%s %s -> %s (carrier=%s)",
                    order.id, order.status, ev.status, ev.carrier_status,
                )

        try:
            db.commit()
        except Exception as exc:
            logger.error("commit failed after polling shipment %s: %s", shipment.id, exc)
            db.rollback()
