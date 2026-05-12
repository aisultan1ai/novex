from __future__ import annotations

import logging
import secrets
import string

from sqlalchemy.orm import Session

from app.modules.shipments.repository import ShipmentsRepository
from app.modules.shipments.schemas import ShipmentResponse

logger = logging.getLogger(__name__)

_ALPHABET = string.ascii_uppercase + string.digits


def _generate_tracking_number(carrier_code: str) -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"{carrier_code.upper()}-{suffix}"


class ShipmentsService:
    def __init__(self, repo: ShipmentsRepository | None = None) -> None:
        self.repo = repo or ShipmentsRepository()

    def create_for_order(
        self,
        db: Session,
        *,
        order_draft_id: int,
        carrier_code: str,
    ) -> ShipmentResponse:
        existing = self.repo.get_by_order_id(db, order_draft_id)
        if existing is not None:
            return ShipmentResponse.model_validate(existing)

        tracking_number = _generate_tracking_number(carrier_code)
        shipment = self.repo.create(
            db,
            order_draft_id=order_draft_id,
            tracking_number=tracking_number,
        )
        logger.info(
            "Shipment created: order_id=%s tracking=%s",
            order_draft_id,
            tracking_number,
        )
        return ShipmentResponse.model_validate(shipment)
