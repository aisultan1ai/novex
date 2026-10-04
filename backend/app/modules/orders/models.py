from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin


class OrderDraft(Base, TimestampMixin):
    __tablename__ = "order_drafts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "quote_session_id",
            name="uq_order_drafts_user_quote_session",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    quote_session_id: Mapped[int] = mapped_column(
        ForeignKey("quote_sessions.id"),
        nullable=False,
        index=True,
    )
    selected_rate_quote_id: Mapped[int] = mapped_column(
        ForeignKey("rate_quotes.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)
    dispatch_error: Mapped[str | None] = mapped_column(String, nullable=True)

    call_before_delivery: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    insurance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fragile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # CSE DeliveryType. One of: door_to_door, warehouse_to_door,
    # door_to_warehouse, warehouse_to_warehouse. PVZ GUIDs are only set for
    # legs that terminate at a CSE PVZ.
    delivery_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="door_to_door"
    )
    sender_pvz_guid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recipient_pvz_guid: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Courier-pickup request (currently only Azimuth /order-courier consumes
    # these; ignored for CSE/Exline). Filled from the shipment form when the
    # customer opts into "вызвать курьера".
    pickup_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Time slot label as the carrier expects it (e.g. "14:00-18:00"). Free
    # string so we can pass through whatever slot the carrier accepts.
    pickup_time_slot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pickup_contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Set after a successful schedule_pickup call — presence of this value
    # blocks re-scheduling for the same order (Azimuth has no dedup key of
    # their own, so we enforce idempotency on our side).
    pickup_scheduled_azimuth_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pickup_error: Mapped[str | None] = mapped_column(String, nullable=True)
    # Waybill(s) left at the carrier after a pickup reschedule whose cancel
    # call failed (comma-separated). Shown as a warning in the admin order
    # card until an operator confirms it was cancelled manually.
    orphan_waybill_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # When the customer confirmed they have consent to pass the sender /
    # recipient personal data (third parties) for this shipment.
    pd_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    carrier_code_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    carrier_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    tariff_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    # CSE-only: frozen at quote-select time so dispatch works even if the
    # RateQuote row was housekept between order creation and dispatch.
    # Nullable because non-CSE carriers do not populate it.
    urgency_guid_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # price_snapshot = customer-facing total = what the customer is charged.
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # carrier_price_snapshot = carrier-side amount (what perevozchik receives).
    # markup_amount_snapshot = the Novex commission / markup on top.
    # Both are nullable so orders created before migration 032 remain valid.
    carrier_price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    markup_amount_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency_snapshot: Mapped[str] = mapped_column(String(3), nullable=False)

    eta_days_min_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_days_max_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)

    from_country_snapshot: Mapped[str] = mapped_column(String(2), nullable=False)
    from_city_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    to_country_snapshot: Mapped[str] = mapped_column(String(2), nullable=False)
    to_city_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    shipment_type_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)

    parties: Mapped[list[ShipmentParty]] = relationship(
        back_populates="order_draft",
        cascade="all, delete-orphan",
    )
    packages: Mapped[list[ShipmentPackage]] = relationship(
        back_populates="order_draft",
        cascade="all, delete-orphan",
    )


class ShipmentParty(Base, TimestampMixin):
    __tablename__ = "shipment_parties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_draft_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # ИИН / БИН отправителя или получателя (12 цифр).
    tax_id: Mapped[str | None] = mapped_column(String(12), nullable=True)

    country: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    order_draft: Mapped[OrderDraft] = relationship(back_populates="parties")


class ShipmentPackage(Base, TimestampMixin):
    __tablename__ = "shipment_packages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_draft_id: Mapped[int] = mapped_column(
        ForeignKey("order_drafts.id"),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    width_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    depth_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    declared_value: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    declared_value_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True
    )

    order_draft: Mapped[OrderDraft] = relationship(back_populates="packages")
