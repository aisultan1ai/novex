from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ShippingQuoteRequest(BaseModel):
    from_country: str = Field(min_length=2, max_length=2)
    from_city: str = Field(min_length=1, max_length=100)
    to_country: str = Field(min_length=2, max_length=2)
    to_city: str = Field(min_length=1, max_length=100)

    shipment_type: str = Field(min_length=1, max_length=20)

    weight_kg: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    width_cm: Decimal = Field(default=Decimal("0"), ge=0)
    height_cm: Decimal = Field(default=Decimal("0"), ge=0)
    depth_cm: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("from_country", "to_country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("from_city", "to_city", "shipment_type")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return value.strip()


class CarrierServiceItem(BaseModel):
    code: str
    name: str
    available: bool
    price: Decimal | None = None
    currency: str = "KZT"
    note: str = ""


class RateQuoteItem(BaseModel):
    id: int | None = None
    carrier_code: str
    carrier_name: str
    tariff_name: str
    price: Decimal
    currency: str
    eta_days_min: int
    eta_days_max: int
    badge: str | None = None
    is_selected: bool = False
    available_services: list[CarrierServiceItem] = []


class ShippingQuoteResponse(BaseModel):
    quote_session_id: int
    public_token: str | None = None
    quotes: list[RateQuoteItem]


class QuoteSelectionRequest(BaseModel):
    rate_quote_id: int = Field(gt=0)
