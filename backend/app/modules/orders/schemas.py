from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DeliveryType = Literal[
    "door_to_door",           # CSE: ДоставкаДоДверей
    "warehouse_to_door",      # CSE: СкладДверь (sender drops at PVZ)
    "door_to_warehouse",      # CSE: Самовывоз (recipient picks up from PVZ)
    "warehouse_to_warehouse", # CSE: СкладСклад (both sides via PVZ)
]

OrderDraftStatus = Literal[
    "draft",
    "shipment_details_completed",
    "ready_for_checkout",
    "awaiting_payment",
    "payment_under_review",
    "payment_rejected",
    "paid",
    "dispatch_queued",
    "sent_to_carrier",
    "picked_up",
    "in_transit",
    "out_for_delivery",
    "arrived",
    "delivery_failed",
    "customs_hold",
    "delivered",
    "return_requested",
    "return_in_progress",
    "returned",
    "cancelled",
    "dispatch_failed",
    "pending_manual",
    "pending_manual_dispatch",
]
ShipmentPartyRole = Literal["sender", "recipient"]


class CreateDraftFromQuoteRequest(BaseModel):
    quote_session_id: int = Field(gt=0)
    public_token: str | None = None


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
    save_to_address_book: bool = False

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("phone")
    @classmethod
    def validate_party_phone(cls, value: str) -> str:
        import re
        digits_only = re.sub(r"[\s\-\(\)]", "", value.strip())
        if not re.match(r"^(\+?7|8)[0-9]{10}$", digits_only):
            raise ValueError(
                "Укажите номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX"
            )
        if digits_only.startswith("8"):
            digits_only = "+7" + digits_only[1:]
        elif digits_only.startswith("7"):
            digits_only = "+" + digits_only
        return digits_only

    @field_validator(
        "full_name",
        "email",
        "company_name",
        "city",
        "address_line1",
        "address_line2",
        "postal_code",
        "comment",
        check_fields=False,
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
    declared_value_currency: str | None = Field(
        default=None, min_length=3, max_length=3
    )

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
    call_before_delivery: bool = False
    insurance: bool = False
    fragile: bool = False

    delivery_type: DeliveryType = "door_to_door"
    # PVZ GUIDs are required only for the corresponding warehouse legs
    # (validated below). Carrier-agnostic today but consumed only by CSE.
    sender_pvz_guid: str | None = Field(default=None, max_length=50)
    recipient_pvz_guid: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _validate_pvz_for_delivery_type(self) -> "UpdateShipmentDetailsRequest":
        sender_leg_wh = self.delivery_type in (
            "warehouse_to_door", "warehouse_to_warehouse"
        )
        recipient_leg_wh = self.delivery_type in (
            "door_to_warehouse", "warehouse_to_warehouse"
        )
        if sender_leg_wh and not self.sender_pvz_guid:
            raise ValueError(
                "sender_pvz_guid обязателен для выбранного типа доставки"
            )
        if recipient_leg_wh and not self.recipient_pvz_guid:
            raise ValueError(
                "recipient_pvz_guid обязателен для выбранного типа доставки"
            )
        # Clear stale PVZ GUIDs on legs that don't use them, so the DB never
        # carries orphan data for a leg the customer later switched away from.
        if not sender_leg_wh:
            self.sender_pvz_guid = None
        if not recipient_leg_wh:
            self.recipient_pvz_guid = None
        return self


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

    from_country_snapshot: str
    from_city_snapshot: str
    to_country_snapshot: str
    to_city_snapshot: str
    shipment_type_snapshot: str
    created_at: datetime

    call_before_delivery: bool = False
    insurance: bool = False
    fragile: bool = False

    delivery_type: DeliveryType = "door_to_door"
    sender_pvz_guid: str | None = None
    recipient_pvz_guid: str | None = None

    sender: ShipmentPartyResponse | None = None
    recipient: ShipmentPartyResponse | None = None
    packages: list[ShipmentPackageResponse]

    tracking_number: str | None = None


class OrderDraftListResponse(BaseModel):
    items: list[OrderDraftResponse]
    total: int
    page: int
    size: int
    pages: int


class CseRecalcRequest(BaseModel):
    """Recalculate CSE quote after the customer picks add-on services.

    Sent in real time from the checkout form; CSE returns the fully-loaded
    tariff so the price shown at the "Pay" button matches what CSE will bill.
    """
    delivery_type: DeliveryType = "door_to_door"
    insurance: bool = False
    declared_value: Decimal | None = Field(default=None, ge=0)


class CseRecalcResponse(BaseModel):
    price: Decimal          # customer-facing total (carrier_price + markup)
    carrier_price: Decimal  # raw CSE amount
    currency: str
    recalculated: bool      # False for non-CSE drafts (silent no-op)
