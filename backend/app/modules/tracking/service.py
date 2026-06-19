from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.common.status_machine import can_transition
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.dispatch.models import OrderStatusHistory
from app.modules.orders.repository import OrdersRepository
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import (
    TrackingEventCreate,
    TrackingEventResponse,
    TrackingHistoryResponse,
)

logger = logging.getLogger(__name__)

_TRACKING_TO_ORDER_STATUS: dict[str, str] = {
    "sent_to_carrier": "sent_to_carrier",
    "picked_up": "picked_up",
    "in_transit": "in_transit",
    "arrived": "arrived",
    "delivered": "delivered",
    "returned": "returned",
    "cancelled": "cancelled",
}


class TrackingService:
    def __init__(
        self,
        tracking_repo: TrackingRepository | None = None,
        orders_repo: OrdersRepository | None = None,
    ) -> None:
        self.tracking_repo = tracking_repo or TrackingRepository()
        self.orders_repo = orders_repo or OrdersRepository()

    def get_tracking(
        self,
        db: Session,
        *,
        user_id: int,
        order_draft_id: int,
    ) -> TrackingHistoryResponse:
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Нет доступа к этому заказу")

        events = self.tracking_repo.list_events(db, order_draft_id=order_draft_id)
        return TrackingHistoryResponse(
            order_draft_id=order_draft_id,
            events=[TrackingEventResponse.model_validate(e) for e in events],
        )

    def add_event(
        self,
        db: Session,
        *,
        order_draft_id: int,
        payload: TrackingEventCreate,
    ) -> TrackingEventResponse:
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")

        event = self.tracking_repo.add_event(
            db,
            order_draft_id=order_draft_id,
            status=payload.status,
            description=payload.description,
            location=payload.location,
            carrier_status=payload.carrier_status,
        )
        new_order_status = _TRACKING_TO_ORDER_STATUS.get(payload.status)
        if new_order_status is not None:
            if can_transition(order.status, new_order_status):
                old_order_status = order.status
                order.status = new_order_status
                db.add(OrderStatusHistory(
                    order_id=order_draft_id,
                    old_status=old_order_status,
                    new_status=new_order_status,
                    source="tracking_event",
                    comment=f"Carrier status: {payload.carrier_status or payload.status}",
                ))
                logger.info(
                    "Order status synced via tracking: order_id=%s %s → %s",
                    order_draft_id,
                    old_order_status,
                    new_order_status,
                )
            else:
                logger.warning(
                    "Tracking event skipped for order status: order_id=%s cannot transition %s → %s",
                    order_draft_id,
                    order.status,
                    new_order_status,
                )

        db.commit()
        logger.info(
            "Tracking event added: order_id=%s status=%s",
            order_draft_id,
            payload.status,
        )
        return TrackingEventResponse.model_validate(event)
