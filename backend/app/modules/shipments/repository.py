from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.shipments.models import Shipment


class ShipmentsRepository:
    def create(
        self,
        db: Session,
        *,
        order_draft_id: int,
        tracking_number: str,
        carrier_tracking_number: str | None = None,
    ) -> Shipment:
        shipment = Shipment(
            order_draft_id=order_draft_id,
            tracking_number=tracking_number,
            carrier_tracking_number=carrier_tracking_number,
            status="created",
        )
        db.add(shipment)
        db.flush()
        return shipment

    def get_by_order_id(self, db: Session, order_draft_id: int) -> Shipment | None:
        return db.scalar(
            select(Shipment).where(Shipment.order_draft_id == order_draft_id)
        )

    def get_by_tracking_number(self, db: Session, tracking_number: str) -> Shipment | None:
        return db.scalar(
            select(Shipment).where(Shipment.tracking_number == tracking_number)
        )
