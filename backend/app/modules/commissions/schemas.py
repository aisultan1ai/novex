from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CommissionResponse(BaseModel):
    id: int
    order_draft_id: int
    carrier_code: str
    gross_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommissionSummary(BaseModel):
    total_gross: Decimal
    total_commission: Decimal
    currency: str
    count: int
