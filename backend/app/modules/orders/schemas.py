from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OrderDraftStatus = Literal["draft", "shipment_details_completed", "ready_for_checkout"]
ShipmentPartyRole = Literal["sender", "recipient"]


class CreateDraftFromQuoteRequest(BaseModel):
    quote_session_id: int = Field(gt=0)


class ShipmentPartyInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)

    country: str = Field(min_length=2, max_length=2)
    city: str = Field(min_length=1, max_length=100)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=50)
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "full_name",
        "phone",
        "email",
        "company_name",
        "city",
        "address_line1",
        "address_line2",
        "postal_code",
        "comment",
    )
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ShipmentPackageInput(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)

    weight_kg: Decimal = Field(gt=0)
    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    depth_cm: Decimal = Field(gt=0)

    declared_value: Decimal | None = Field(default=None, ge=0)
    declared_value_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("declared_value_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class UpdateShipmentDetailsRequest(BaseModel):
    sender: ShipmentPartyInput
    recipient: ShipmentPartyInput
    packages: list[ShipmentPackageInput] = Field(min_length=1)


class ShipmentPartyResponse(BaseModel):
    id: int
    role: ShipmentPartyRole

    full_name: str
    phone: str
    email: str | None
    company_name: str | None

    country: str
    city: str
    address_line1: str
    address_line2: str | None
    postal_code: str | None
    comment: str | None


class ShipmentPackageResponse(BaseModel):
    id: int
    description: str
    quantity: int

    weight_kg: Decimal
    width_cm: Decimal
    height_cm: Decimal
    depth_cm: Decimal

    declared_value: Decimal | None
    declared_value_currency: str | None


class OrderDraftResponse(BaseModel):
    draft_id: int
    user_id: int
    quote_session_id: int
    selected_rate_quote_id: int
    status: OrderDraftStatus

    carrier_code_snapshot: str
    carrier_name_snapshot: str
    tariff_name_snapshot: str
    price_snapshot: Decimal
    currency_snapshot: str
    eta_days_min_snapshot: int
    eta_days_max_snapshot: int

    sender: ShipmentPartyResponse | None = None
    recipient: ShipmentPartyResponse | None = None
    packages: list[ShipmentPackageResponse]