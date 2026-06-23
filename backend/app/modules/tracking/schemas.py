from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrackingEventCreate(BaseModel):
    status: str
    description: str | None = None
    location: str | None = None
    carrier_status: str | None = None


class TrackingEventResponse(BaseModel):
    id: int
    order_draft_id: int
    status: str
    description: str | None
    location: str | None
    carrier_status: str | None
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackingHistoryResponse(BaseModel):
    order_draft_id: int
    events: list[TrackingEventResponse]


class PublicTrackingEventResponse(BaseModel):
    status: str
    description: str | None
    location: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


class PublicTrackingResponse(BaseModel):
    tracking_number: str
    carrier_name: str
    from_city: str
    to_city: str
    order_status: str
    eta_days_min: int
    eta_days_max: int
    created_at: datetime
    events: list[PublicTrackingEventResponse]
