from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal

import httpx

from app.modules.payments.providers.base import (
    InitiatePaymentResult,
    ParsedWebhookEvent,
    PaymentProvider,
)

logger = logging.getLogger(__name__)

_STATUS_MAP: dict[str, str] = {
    "APPROVED": "paid",
    "PAID": "paid",
    "FAILED": "payment_rejected",
    "CANCELLED": "cancelled",
    "DECLINED": "payment_rejected",
}


class KaspiProvider(PaymentProvider):
    """Kaspi Pay — disabled by default until merchant onboarding is complete."""

    provider_code = "kaspi"

    def __init__(
        self,
        *,
        merchant_id: str,
        api_key: str,
        api_url: str,
        webhook_secret: str,
        frontend_url: str,
        backend_url: str,
    ) -> None:
        self._merchant_id = merchant_id
        self._api_key = api_key
        self._api_url = api_url
        self._webhook_secret = webhook_secret
        self._frontend_url = frontend_url
        self._backend_url = backend_url

    def initiate_payment(
        self,
        *,
        order_id: int,
        amount: Decimal,
        currency: str,
        description: str,
    ) -> InitiatePaymentResult:
        payload = {
            "MerchantId": self._merchant_id,
            "OrderId": str(order_id),
            "Amount": int(amount * 100),
            "Currency": currency,
            "Description": description,
            "ReturnUrl": f"{self._frontend_url}/dashboard/orders?payment=success&order={order_id}",
            "FailUrl": f"{self._frontend_url}/dashboard/orders?payment=fail&order={order_id}",
            "CallbackUrl": f"{self._backend_url}/api/v1/payments/kaspi/webhook",
        }
        resp = httpx.post(
            f"{self._api_url}/payments/create",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "X-Merchant-Id": self._merchant_id,
            },
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return InitiatePaymentResult(
            payment_url=data["PaymentUrl"],
            external_payment_id=data["PaymentId"],
            payment_reference=str(order_id),
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("x-kaspi-signature", "")
        if not signature or not self._webhook_secret:
            return False
        expected = hmac.new(
            self._webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.lower())

    def parse_webhook(self, raw_body: bytes, headers: dict[str, str]) -> ParsedWebhookEvent:
        body = json.loads(raw_body)
        order_id = str(body.get("OrderId") or body.get("orderId", ""))
        raw_status = str(body.get("Status") or body.get("status", "")).upper()
        external_id = str(body.get("PaymentId") or body.get("paymentId", ""))
        amount_raw = body.get("Amount") or body.get("amount")
        amount = Decimal(str(amount_raw)) / 100 if amount_raw is not None else None

        return ParsedWebhookEvent(
            external_payment_id=external_id,
            external_event_id=external_id or hashlib.sha256(raw_body).hexdigest(),
            order_id=order_id or None,
            status=_STATUS_MAP.get(raw_status, ""),
            amount=amount,
            raw=body,
        )

    def refund_payment(self, *, external_payment_id: str, amount: Decimal) -> bool:
        logger.info("Kaspi refund: payment_id=%s amount=%s", external_payment_id, amount)
        raise NotImplementedError("Kaspi refund not yet implemented")
