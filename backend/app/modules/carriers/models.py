"""
carriers/models.py — SQLAlchemy-модели для хранения тарифов.
Спроектированы под будущую загрузку тарифов через Excel в admin-панели.
"""

from __future__ import annotations
from datetime import date
from sqlalchemy import (
    Boolean, Column, Date, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.core.db import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    services = relationship("CarrierService", back_populates="carrier", cascade="all, delete-orphan")
    zone_cities = relationship("CarrierZoneCity", back_populates="carrier", cascade="all, delete-orphan")


class CarrierService(Base):
    __tablename__ = "carrier_services"
    __table_args__ = (UniqueConstraint("carrier_id", "code", name="uq_carrier_service_code"),)

    id = Column(Integer, primary_key=True)
    carrier_id = Column(Integer, ForeignKey("carriers.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    shipment_type = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    carrier = relationship("Carrier", back_populates="services")
    tariff_rates = relationship("CarrierTariffRate", back_populates="service", cascade="all, delete-orphan")


class CarrierTariffRate(Base):
    __tablename__ = "carrier_tariff_rates"

    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("carrier_services.id", ondelete="CASCADE"), nullable=False)
    zone = Column(Integer, nullable=False)
    weight_from_kg = Column(Numeric(10, 3), nullable=False, default=0)
    weight_to_kg = Column(Numeric(10, 3), nullable=True)
    base_price = Column(Numeric(12, 2), nullable=False)
    per_unit_price = Column(Numeric(12, 2), nullable=True)
    per_unit_weight_kg = Column(Numeric(10, 3), nullable=True)
    currency = Column(String(10), default="KZT", nullable=False)
    eta_days_min = Column(Integer, nullable=True)
    eta_days_max = Column(Integer, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    effective_from = Column(Date, nullable=False, default=date.today)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    service = relationship("CarrierService", back_populates="tariff_rates")


class CarrierZoneCity(Base):
    __tablename__ = "carrier_zone_cities"
    __table_args__ = (UniqueConstraint("carrier_id", "city_name_normalized", name="uq_carrier_city"),)

    id = Column(Integer, primary_key=True)
    carrier_id = Column(Integer, ForeignKey("carriers.id", ondelete="CASCADE"), nullable=False)
    city_name = Column(String(255), nullable=False)
    city_name_normalized = Column(String(255), nullable=False, index=True)
    zone = Column(Integer, nullable=False)
    city_type = Column(String(50), nullable=True)

    carrier = relationship("Carrier", back_populates="zone_cities")