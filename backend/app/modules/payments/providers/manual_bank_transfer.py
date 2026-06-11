from __future__ import annotations

from decimal import Decimal

from app.modules.payments.providers.base import (
    InitiatePaymentResult,
    ParsedWebhookEvent,
    PaymentProvider,
)


class ManualBankTransferProvider(PaymentProvider):
    """Manual bank transfer — customer pays via bank and uploads a proof screenshot."""

    provider_code = "manual_bank_transfer"

    def __init__(
        self,
        *,
        recipient_name: str,
        bank_name: str,
        iban: str,
        bin_number: str,
        knp: str,
    ) -> None:
        self._recipient_name = recipient_name
        self._bank_name = bank_name
        self._iban = iban
        self._bin = bin_number
        self._knp = knp

    def initiate_payment(
        self,
        *,
        order_id: int,
        amount: Decimal,
        currency: str,
        description: str,
    ) -> InitiatePaymentResult:
        return InitiatePaymentResult(
            payment_url=None,
            external_payment_id=None,
            payment_reference=f"NOVEX-{order_id:06d}",
            metadata={
                "recipient_name": self._recipient_name,
                "bank_name": self._bank_name,
                "iban": self._iban,
                "bin": self._bin,
                "knp": self._knp,
                "purpose": f"Оплата доставки по заказу NOVEX-{order_id:06d}",
                "amount": str(amount),
                "currency": currency,
            },
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        # No inbound webhooks for manual bank transfer
        return False

    def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ParsedWebhookEvent:
        raise NotImplementedError("Manual bank transfer does not support inbound webhooks")

    def refund_payment(self, *, external_payment_id: str, amount: Decimal) -> bool:
        # Bank transfer refunds are manual: operator sends money back via bank.
        # Returning True acknowledges the refund is recorded; actual transfer is offline.
        return True

    def get_bank_details(self) -> dict:
        return {
            "recipient_name": self._recipient_name,
            "bank_name": self._bank_name,
            "iban": self._iban,
            "bin": self._bin,
            "knp": self._knp,
        }
