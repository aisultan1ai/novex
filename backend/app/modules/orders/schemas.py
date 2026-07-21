from __future__ import annotations

from datetime import date, datetime
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
    tax_id: str = Field(min_length=12, max_length=12, description="ИИН / БИН — 12 цифр")

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

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit() or len(cleaned) != 12:
            raise ValueError("ИИН / БИН должен состоять ровно из 12 цифр")
        return cleaned

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

    # Courier-pickup request (Azimuth /order-courier). Optional — customer
    # opts in on the shipment form. `pickup_requested=True` requires the
    # date + slot + contact person to be provided (see _validate_pickup).
    pickup_requested: bool = False
    pickup_date: date | None = None
    pickup_time_slot: str | None = Field(default=None, max_length=50)
    pickup_contact_person: str | None = Field(default=None, max_length=255)
    pickup_contact_phone: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _validate_pickup(self) -> "UpdateShipmentDetailsRequest":
        if not self.pickup_requested:
            # Wipe stale pickup fields when the flag is off so a toggle-off
            # never leaves orphan values in the DB.
            self.pickup_date = None
            self.pickup_time_slot = None
            self.pickup_contact_person = None
            self.pickup_contact_phone = None
            return self
        if not self.pickup_date:
            raise ValueError("pickup_date обязателен при вызове курьера")
        if not self.pickup_time_slot:
            raise ValueError("pickup_time_slot обязателен при вызове курьера")
        # Contact defaults to the sender if the customer left it blank —
        # they are the person the courier will actually meet.
        if not self.pickup_contact_person:
            self.pickup_contact_person = self.sender.full_name
        if not self.pickup_contact_phone:
            self.pickup_contact_phone = self.sender.phone
        return self

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
    tax_id: str | None

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

    pickup_requested: bool = False
    pickup_date: date | None = None
    pickup_time_slot: str | None = None
    pickup_contact_person: str | None = None
    pickup_contact_phone: str | None = None
    # Set to True by dispatch worker once schedule_pickup succeeded once —
    # the front-end uses this to render "курьер вызван" instead of the
    # generic pickup section.
    pickup_scheduled: bool = False
    pickup_error: str | None = None

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
    """Recalculate a draft's price for the current carrier/tariff.

    Sent live from the shipment/checkout form. CSE drafts re-hit the CSE Calc
    API for a fully-loaded amount (services + declared value). Other carriers
    fall back to the tariff engine using the (optionally overridden) package
    weight/dimensions/quantity so the "Pay" price reflects the actual parcel.
    """
    delivery_type: DeliveryType = "door_to_door"
    insurance: bool = False
    declared_value: Decimal | None = Field(default=None, ge=0)
    # Optional per-package overrides. When present, they replace the
    # quote_session weight/dims for this recalc (does not persist).
    weight_kg: Decimal | None = Field(default=None, gt=0)
    width_cm: Decimal | None = Field(default=None, gt=0)
    height_cm: Decimal | None = Field(default=None, gt=0)
    depth_cm: Decimal | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, ge=1)


class CseRecalcResponse(BaseModel):
    price: Decimal          # customer-facing total (carrier_price + markup)
    carrier_price: Decimal  # raw carrier amount
    currency: str
    recalculated: bool      # True if the engine produced a fresh number
