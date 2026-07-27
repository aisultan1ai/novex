from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.limiter import limiter
from app.modules.orders.models import OrderDraft
from app.modules.shipments.models import Shipment
from app.modules.tracking.repository import TrackingRepository
from app.modules.tracking.schemas import (
    DeliveryInfo,
    PublicTrackingEventResponse,
    PublicTrackingResponse,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])
_tracking_repo = TrackingRepository()


@router.get(
    "/{tracking_number}",
    response_model=PublicTrackingResponse,
    summary="Публичное отслеживание по номеру",
)
@limiter.limit("60/minute")
def get_public_tracking(
    request: Request,
    tracking_number: str,
    db: Session = Depends(get_db),
) -> PublicTrackingResponse:
    shipment = db.scalar(
        select(Shipment).where(Shipment.tracking_number == tracking_number)
    )
    if shipment is None:
        raise HTTPException(status_code=404, detail="Номер отслеживания не найден")

    order = db.scalar(
        select(OrderDraft).where(OrderDraft.id == shipment.order_draft_id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    events = _tracking_repo.list_events(db, order_draft_id=order.id)

    # Public endpoint — только время доставки. ФИО/адрес получателя намеренно
    # не отдаются, чтобы трек-номер не превращался в утечку PII (кто угодно,
    # знающий номер, иначе бы видел получателя и его адрес).
    delivery: DeliveryInfo | None = None
    delivered_event = next(
        (e for e in reversed(events) if e.status == "delivered"), None
    )
    if delivered_event is not None:
        delivery = DeliveryInfo(delivered_at=delivered_event.occurred_at)

    return PublicTrackingResponse(
        tracking_number=tracking_number,
        carrier_code=order.carrier_code_snapshot,
        carrier_name=order.carrier_name_snapshot,
        from_city=order.from_city_snapshot,
        to_city=order.to_city_snapshot,
        order_status=order.status,
        eta_days_min=order.eta_days_min_snapshot,
        eta_days_max=order.eta_days_max_snapshot,
        created_at=order.created_at,
        events=[
            PublicTrackingEventResponse(
                status=e.status,
                description=e.description,
                location=e.location,
                occurred_at=e.occurred_at,
            )
            for e in events
        ],
        delivery=delivery,
    )
