from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    id: int
    order_draft_id: int
    user_id: int
    carrier_code: str
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CarrierRatingSummary(BaseModel):
    carrier_code: str
    avg_rating: float
    count: int


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    size: int
    pages: int
