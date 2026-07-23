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
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)

_DISPATCH_TIMEOUT = 60  # carrier invoice creation can be slow
_TRACKING_TIMEOUT = 30
_TEST_TIMEOUT = 20

# Shared connection pool: keeps TCP connections alive between requests,
# avoiding per-request handshake overhead under polling/dispatch load.
_HTTP_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=20)


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
        # Persistent client with connection pooling — reuses TCP sockets across
        # repeated dispatch/tracking calls instead of opening a new connection each time.
        self._client = httpx.Client(limits=_HTTP_LIMITS)

    def _headers(self) -> dict[str, str]:
        headers = {"X-Gateway-Secret": self._secret}
        # Forward the caller's trace id so gateway logs correlate with API +
        # worker logs. Missing id (bootstrap / test) simply omits the header.
        rid = get_request_id()
        if rid:
            headers["X-Request-Id"] = rid
        return headers

    def _post_with_retry(self, url: str, *, json: dict, timeout: int) -> httpx.Response:
        """POST with one automatic retry on stale-connection errors.

        httpx keeps TCP connections alive in a pool. If the carrier-gateway
        container restarts, the pooled sockets become stale and the next
        request raises RemoteProtocolError / ConnectError with an empty or
        misleading message. We catch those, close the client, open a fresh
        one, and retry once so the dispatch job doesn't fail spuriously.
        """
        try:
            return self._client.post(url, json=json, headers=self._headers(), timeout=timeout)
        except (httpx.RemoteProtocolError, httpx.ConnectError) as exc:
            logger.warning("Gateway stale-connection error, reopening client and retrying: %r", exc)
            try:
                self._client.close()
            except Exception:
                pass
            self._client = httpx.Client(limits=_HTTP_LIMITS)
            return self._client.post(url, json=json, headers=self._headers(), timeout=timeout)

    def create_invoice(
        self, carrier_code: str, order_data: dict, creds: dict
    ) -> GatewayInvoiceResult:
        resp = self._post_with_retry(
            f"{self._base_url}/invoke/create-invoice",
            json={"carrier_code": carrier_code, "order_data": order_data, "creds": creds},
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
        resp = self._post_with_retry(
            f"{self._base_url}/invoke/fetch-tracking",
            json={"carrier_code": carrier_code, "tracking_number": tracking_number, "creds": creds},
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
        resp = self._post_with_retry(
            f"{self._base_url}/invoke/test-connection",
            json={"carrier_code": carrier_code, "creds": creds},
            timeout=_TEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def get_invoice_pdf(self, carrier_code: str, invoice_id: str, creds: dict) -> bytes:
        resp = self._post_with_retry(
            f"{self._base_url}/invoke/get-invoice-pdf",
            json={"carrier_code": carrier_code, "invoice_id": invoice_id, "creds": creds},
            timeout=_DISPATCH_TIMEOUT,
        )
        self._raise_for_carrier_error(resp)
        return base64.b64decode(resp.json()["waybill_pdf_b64"])

    def cancel_invoice(self, carrier_code: str, invoice_id: str, creds: dict) -> bool:
        resp = self._post_with_retry(
            f"{self._base_url}/invoke/cancel-invoice",
            json={"carrier_code": carrier_code, "invoice_id": invoice_id, "creds": creds},
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
