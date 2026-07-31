from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CancellationRequestCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class CancellationRequestResolve(BaseModel):
    # Comment surfaced back to the customer on rejection; optional on approval.
    comment: str | None = Field(default=None, max_length=500)


class CancellationRequestResponse(BaseModel):
    id: int
    order_draft_id: int
    requested_by_user_id: int
    carrier_code: str
    reason: str
    status: str
    api_attempted: bool
    api_error: str | None = None
    carrier_response: str | None = None
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CancellationRequestListResponse(BaseModel):
    items: list[CancellationRequestResponse]
    total: int
    page: int
    size: int
    pages: int
