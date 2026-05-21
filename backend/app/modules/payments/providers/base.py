from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class InitiatePaymentResult:
    payment_url: str | None
    external_payment_id: str | None
    payment_reference: str | None
    metadata: dict | None = None


@dataclass
class ParsedWebhookEvent:
    external_payment_id: str
    external_event_id: str
    order_id: str | None
    status: str
    amount: Decimal | None
    raw: dict


class PaymentProvider(ABC):
    provider_code: str

    @abstractmethod
    def initiate_payment(
        self,
        *,
        order_id: int,
        amount: Decimal,
        currency: str,
        description: str,
    ) -> InitiatePaymentResult:
        ...

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        ...

    @abstractmethod
    def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ParsedWebhookEvent:
        ...

    @abstractmethod
    def refund_payment(self, *, external_payment_id: str, amount: Decimal) -> bool:
        ...
