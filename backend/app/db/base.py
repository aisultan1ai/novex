from __future__ import annotations

from app.core.db import Base
from app.modules.identity.models import CustomerProfile, Role, User
from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.quotes.models import QuoteSession, RateQuote
from app.modules.carriers.models import Carrier, CarrierService, CarrierTariffRate, CarrierZoneCity  # ← добавь

__all__ = [
    "Base",
    "Role",
    "User",
    "CustomerProfile",
    "QuoteSession",
    "RateQuote",
    "OrderDraft",
    "ShipmentParty",
    "ShipmentPackage",
    "Carrier",
    "CarrierService",
    "CarrierTariffRate",
    "CarrierZoneCity",
]