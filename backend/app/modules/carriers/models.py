"""
carriers/models.py — SQLAlchemy-модели для хранения тарифов.
Спроектированы под будущую загрузку тарифов через Excel в admin-панели.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    services: Mapped[list[CarrierService]] = relationship(
        "CarrierService", back_populates="carrier", cascade="all, delete-orphan"
    )
    zone_cities: Mapped[list[CarrierZoneCity]] = relationship(
        "CarrierZoneCity", back_populates="carrier", cascade="all, delete-orphan"
    )


class CarrierService(Base):
    __tablename__ = "carrier_services"
    __table_args__ = (
        UniqueConstraint("carrier_id", "code", name="uq_carrier_service_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carriers.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shipment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    carrier: Mapped[Carrier] = relationship("Carrier", back_populates="services")
    tariff_rates: Mapped[list[CarrierTariffRate]] = relationship(
        "CarrierTariffRate", back_populates="service", cascade="all, delete-orphan"
    )


class CarrierTariffRate(Base):
    __tablename__ = "carrier_tariff_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("carrier_services.id", ondelete="CASCADE"), nullable=False
    )
    zone: Mapped[int] = mapped_column(nullable=False)
    weight_from_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=0
    )
    weight_to_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    per_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    per_unit_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="KZT", nullable=False
    )
    eta_days_min: Mapped[int | None] = mapped_column(nullable=True)
    eta_days_max: Mapped[int | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    effective_from: Mapped[date] = mapped_column(
        nullable=False, default=date.today
    )
    effective_to: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    service: Mapped[CarrierService] = relationship(
        "CarrierService", back_populates="tariff_rates"
    )


class CarrierCommissionConfig(Base):
    __tablename__ = "carrier_commission_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    carrier_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    commission_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="percentage"
    )
    commission_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    fixed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KZT")


class CarrierZoneCity(Base):
    __tablename__ = "carrier_zone_cities"
    __table_args__ = (
        UniqueConstraint("carrier_id", "city_name_normalized", name="uq_carrier_city"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carriers.id", ondelete="CASCADE"), nullable=False
    )
    city_name: Mapped[str] = mapped_column(String(255), nullable=False)
    city_name_normalized: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    zone: Mapped[int] = mapped_column(nullable=False)
    city_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    carrier: Mapped[Carrier] = relationship("Carrier", back_populates="zone_cities")
