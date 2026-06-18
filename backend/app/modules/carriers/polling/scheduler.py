from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.carriers.polling.registry import get_adapter
from app.modules.notifications.service import NotificationsService
from app.modules.shipments.models import Shipment
from app.modules.tracking.models import TrackingEvent
from app.modules.tracking.repository import TrackingRepository

logger = logging.getLogger(__name__)

_tracking_repo = TrackingRepository()
_notifications_svc = NotificationsService()

_ACTIVE_STATUSES = {"sent_to_carrier", "dispatched", "picked_up", "in_transit", "out_for_delivery"}


def poll_all_active_shipments(db: Session) -> None:
    from app.modules.orders.models import OrderDraft

    shipments = db.scalars(
        select(Shipment)
        .join(OrderDraft, OrderDraft.id == Shipment.order_draft_id)
        .where(OrderDraft.status.in_(_ACTIVE_STATUSES))
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

        try:
            events = adapter.fetch_status(shipment.carrier_tracking_number)
        except Exception as exc:
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
