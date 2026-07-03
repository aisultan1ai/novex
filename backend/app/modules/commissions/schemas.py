from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CommissionResponse(BaseModel):
    id: int
    order_draft_id: int
    carrier_code: str
    gross_amount: Decimal
    carrier_payout: Decimal | None = None
    commission_rate: Decimal
    commission_amount: Decimal
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommissionSummary(BaseModel):
    total_gross: Decimal            # what customers paid (turnover)
    total_carrier_payout: Decimal   # what perevozchiks are owed
    total_commission: Decimal       # Novex profit / markup
    currency: str
    count: int
