from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_serializer


# Pydantic v2 по умолчанию сериализует Decimal в string. Фронт типизирует
# соответствующие поля как number и делает арифметику (total_commission /
# total_gross, total_gross > 0), которая на строках даёт NaN / некорректные
# ветки. Явно приводим к float, чтобы JSON был {"total_gross": 12000.0}
# вместо {"total_gross": "12000.00"}. Копейки не теряем — float(Decimal)
# сохраняет два знака в разумных денежных диапазонах KZT.
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
    status: str = "active"
    reverses_commission_id: int | None = None
    reversed_at: datetime | None = None
    reversal_reason: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("gross_amount", "carrier_payout", "commission_rate", "commission_amount")
    def _decimal_to_float(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class CommissionSummary(BaseModel):
    total_gross: Decimal            # what customers paid (turnover)
    total_carrier_payout: Decimal   # what perevozchiks are owed
    total_commission: Decimal       # Novex profit / markup
    currency: str
    count: int

    @field_serializer("total_gross", "total_carrier_payout", "total_commission")
    def _decimal_to_float(self, value: Decimal) -> float:
        return float(value)
