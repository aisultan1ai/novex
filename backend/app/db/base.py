from __future__ import annotations

from app.core.db import Base
from app.modules.cancellations.models import CancellationRequest
from app.modules.carriers.models import (
    Carrier,
    CarrierCommissionConfig,
    CarrierService,
    CarrierTariffRate,
    CarrierZoneCity,
)
from app.modules.dispatch.models import DispatchJob, OrderStatusHistory
from app.modules.documents.models import Document
from app.modules.identity.models import CustomerProfile, Role, User
from app.modules.notifications.models import Notification, NotificationJob
from app.modules.orders.models import OrderDraft, ShipmentPackage, ShipmentParty
from app.modules.payments.transaction_models import (
    PaymentProof,
    PaymentStatusHistory,
    PaymentTransaction,
    ProviderWebhookEvent,
)
from app.modules.quotes.models import QuoteSession, RateQuote
from app.modules.reviews.models import Review
from app.modules.tracking.models import TrackingWebhookEvent

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
    "CarrierCommissionConfig",
    "CancellationRequest",
    "Review",
    "PaymentTransaction",
    "PaymentProof",
    "PaymentStatusHistory",
    "ProviderWebhookEvent",
    "TrackingWebhookEvent",
    "DispatchJob",
    "OrderStatusHistory",
    "Document",
    "Notification",
    "NotificationJob",
]
