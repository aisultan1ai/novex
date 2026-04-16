from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


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

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    carrier_code_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    carrier_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    tariff_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency_snapshot: Mapped[str] = mapped_column(String(3), nullable=False)

    eta_days_min_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_days_max_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)

    parties: Mapped[list["ShipmentParty"]] = relationship(
        back_populates="order_draft",
        cascade="all, delete-orphan",
    )
    packages: Mapped[list["ShipmentPackage"]] = relationship(
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

    country: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    order_draft: Mapped["OrderDraft"] = relationship(back_populates="parties")


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

    declared_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    declared_value_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    order_draft: Mapped["OrderDraft"] = relationship(back_populates="packages")