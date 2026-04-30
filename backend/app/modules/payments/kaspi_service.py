"""
Kaspi Pay integration.

Docs: https://kaspi.kz/o/business  (раздел "API для разработчиков")
После регистрации мерчанта Kaspi выдаёт:
  - KASPI_MERCHANT_ID
  - KASPI_API_KEY
  - KASPI_WEBHOOK_SECRET  (для проверки подписи колбэков)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class KaspiPaymentResult:
    payment_url: str
    kaspi_payment_id: str


class KaspiPayService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.kaspi_api_key}",
            "X-Merchant-Id": self._settings.kaspi_merchant_id,
        }

    def create_payment(
        self,
        *,
        order_id: int,
        amount_kzt: float,
        description: str,
    ) -> KaspiPaymentResult:
        """
        Создаёт платёж в Kaspi Pay и возвращает URL для редиректа клиента.

        Точные поля запроса — из документации мерчанта Kaspi.
        Ниже приведён типичный формат; скорректируй если Kaspi выдаст другую схему.
        """
        settings = self._settings
        payload = {
            "MerchantId": settings.kaspi_merchant_id,
            "OrderId": str(order_id),
            "Amount": round(amount_kzt * 100),  # в тиынах (kopeck-equivalent)
            "Currency": "KZT",
            "Description": description,
            "ReturnUrl": f"{settings.frontend_url}/dashboard/orders?payment=success&order={order_id}",
            "FailUrl":   f"{settings.frontend_url}/dashboard/orders?payment=fail&order={order_id}",
            "CallbackUrl": f"{settings.backend_url}/api/v1/payments/kaspi/webhook",
        }

        resp = httpx.post(
            f"{settings.kaspi_api_url}/payments/create",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # Kaspi возвращает PaymentUrl и PaymentId — имена полей уточни по доке
        return KaspiPaymentResult(
            payment_url=data["PaymentUrl"],
            kaspi_payment_id=data["PaymentId"],
        )

    def verify_webhook(self, raw_body: bytes, signature_header: str) -> bool:
        """
        Проверяет HMAC-SHA256 подпись входящего колбэка от Kaspi.
        Ключ — KASPI_WEBHOOK_SECRET из настроек.
        """
        expected = hmac.new(
            key=self._settings.kaspi_webhook_secret.encode(),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header.lower())

    def parse_webhook(self, body: dict) -> tuple[str, str]:
        """
        Разбирает тело колбэка.
        Возвращает (order_id, status) где status: 'paid' | 'failed' | 'cancelled'
        Поля уточни по документации Kaspi.
        """
        order_id = body.get("OrderId") or body.get("orderId", "")
        raw_status = body.get("Status") or body.get("status", "")

        # Маппинг статусов Kaspi → наши статусы
        STATUS_MAP: dict[str, str] = {
            "APPROVED": "paid",
            "PAID":     "paid",
            "FAILED":   "cancelled",
            "CANCELLED": "cancelled",
            "DECLINED": "cancelled",
        }
        our_status = STATUS_MAP.get(raw_status.upper(), "")
        return str(order_id), our_status
