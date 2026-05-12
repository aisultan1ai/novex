from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.orders.repository import OrdersRepository
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import (
    TrackingEventCreate,
    TrackingEventResponse,
    TrackingHistoryResponse,
)

logger = logging.getLogger(__name__)


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
        db.commit()
        logger.info(
            "Tracking event added: order_id=%s status=%s",
            order_draft_id,
            payload.status,
        )
        return TrackingEventResponse.model_validate(event)
