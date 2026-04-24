from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class QuoteSession(Base):
    __tablename__ = "quote_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    from_country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    from_city: Mapped[str] = mapped_column(String(100), nullable=False)
    to_country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    to_city: Mapped[str] = mapped_column(String(100), nullable=False)

    shipment_type: Mapped[str] = mapped_column(String(20), nullable=False)

    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    width_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    depth_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    rate_quotes: Mapped[list["RateQuote"]] = relationship(
        back_populates="quote_session",
        cascade="all, delete-orphan",
    )


class RateQuote(Base):
    __tablename__ = "rate_quotes"
    __table_args__ = (
        Index("ix_rate_quotes_session_selected", "quote_session_id", "is_selected"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quote_session_id: Mapped[int] = mapped_column(
        ForeignKey("quote_sessions.id"),
        nullable=False,
        index=True,
    )

    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    carrier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tariff_name: Mapped[str] = mapped_column(String(100), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")

    eta_days_min: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_days_max: Mapped[int] = mapped_column(Integer, nullable=False)

    badge: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_selected: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=False,
    )

    quote_session: Mapped["QuoteSession"] = relationship(back_populates="rate_quotes")