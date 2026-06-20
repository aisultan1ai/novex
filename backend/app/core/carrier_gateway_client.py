"""
Internal HTTP client for the carrier-gateway service.

Used by dispatch/service.py, polling/scheduler.py, and admin_carrier_api.py
to call carrier API clients through the dedicated gateway container.
Credentials are fetched from DB by the caller and passed in each request —
the gateway itself has no DB access.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_DISPATCH_TIMEOUT = 60  # carrier invoice creation can be slow
_TRACKING_TIMEOUT = 30
_TEST_TIMEOUT = 20


@dataclass
class GatewayInvoiceResult:
    waybill_number: str
    carrier_invoice_id: str | None
    waybill_pdf_bytes: bytes | None


@dataclass
class GatewayTrackingEvent:
    status: str
    carrier_status: str
    location: str | None
    occurred_at: datetime
    description: str | None


class CarrierGatewayClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.carrier_gateway_url.rstrip("/")
        self._secret = settings.gateway_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Gateway-Secret": self._secret}

    def create_invoice(
        self, carrier_code: str, order_data: dict, creds: dict
    ) -> GatewayInvoiceResult:
        resp = httpx.post(
            f"{self._base_url}/invoke/create-invoice",
            json={"carrier_code": carrier_code, "order_data": order_data, "creds": creds},
            headers=self._headers(),
            timeout=_DISPATCH_TIMEOUT,
        )
        self._raise_for_carrier_error(resp)
        data = resp.json()
        pdf_bytes = base64.b64decode(data["waybill_pdf_b64"]) if data.get("waybill_pdf_b64") else None
        return GatewayInvoiceResult(
            waybill_number=data["waybill_number"],
            carrier_invoice_id=data.get("carrier_invoice_id"),
            waybill_pdf_bytes=pdf_bytes,
        )

    def fetch_tracking(
        self, carrier_code: str, tracking_number: str, creds: dict
    ) -> list[GatewayTrackingEvent]:
        resp = httpx.post(
            f"{self._base_url}/invoke/fetch-tracking",
            json={"carrier_code": carrier_code, "tracking_number": tracking_number, "creds": creds},
            headers=self._headers(),
            timeout=_TRACKING_TIMEOUT,
        )
        self._raise_for_carrier_error(resp)
        return [
            GatewayTrackingEvent(
                status=e["status"],
                carrier_status=e["carrier_status"],
                location=e.get("location"),
                occurred_at=datetime.fromisoformat(e["occurred_at"]),
                description=e.get("description"),
            )
            for e in resp.json()["events"]
        ]

    def test_connection(self, carrier_code: str, creds: dict) -> dict:
        resp = httpx.post(
            f"{self._base_url}/invoke/test-connection",
            json={"carrier_code": carrier_code, "creds": creds},
            headers=self._headers(),
            timeout=_TEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def cancel_invoice(self, carrier_code: str, invoice_id: str, creds: dict) -> bool:
        resp = httpx.post(
            f"{self._base_url}/invoke/cancel-invoice",
            json={"carrier_code": carrier_code, "invoice_id": invoice_id, "creds": creds},
            headers=self._headers(),
            timeout=_TEST_TIMEOUT,
        )
        self._raise_for_carrier_error(resp)
        return resp.json().get("ok", False)

    @staticmethod
    def _raise_for_carrier_error(resp: httpx.Response) -> None:
        """Translate gateway 502 (carrier error) into RuntimeError with carrier's message."""
        if resp.status_code == 502:
            detail = resp.json().get("detail", resp.text)
            raise RuntimeError(detail)
        resp.raise_for_status()


@lru_cache(maxsize=1)
def get_gateway_client() -> CarrierGatewayClient:
    return CarrierGatewayClient()
