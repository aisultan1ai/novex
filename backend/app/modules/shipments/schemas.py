from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ShipmentResponse(BaseModel):
    id: int
    order_draft_id: int
    tracking_number: str
    carrier_tracking_number: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
