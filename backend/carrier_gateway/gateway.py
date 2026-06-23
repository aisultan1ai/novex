"""
Carrier Gateway — internal service wrapping external carrier HTTP APIs.

Responsibilities:
  - Receive order_data + creds from backend/poller (no DB access here)
  - Call Exline / Azimuth APIs and normalise responses
  - Auth: X-Gateway-Secret shared secret (service-to-service only)

Never exposed to the public internet — internal Docker network only.
"""
from __future__ import annotations

import base64
import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.modules.carriers.api_clients.registry import get_client, list_supported_codes
from app.modules.carriers.polling.registry import get_adapter

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

_GATEWAY_SECRET = os.environ.get("GATEWAY_SECRET", "")
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

if _ENVIRONMENT == "production" and not _GATEWAY_SECRET:
    raise RuntimeError(
        "GATEWAY_SECRET must be set in production — "
        "generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

app = FastAPI(
    title="Carrier Gateway",
    description="Internal service — not for public use",
    docs_url=None,   # disable swagger on internal service
    redoc_url=None,
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def verify_secret(x_gateway_secret: str = Header(default="")) -> None:
    if _GATEWAY_SECRET and x_gateway_secret != _GATEWAY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid gateway secret")


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateInvoiceRequest(BaseModel):
    carrier_code: str
    order_data: dict
    creds: dict


class CreateInvoiceResponse(BaseModel):
    waybill_number: str
    carrier_invoice_id: str | None = None
    waybill_pdf_b64: str | None = None


class FetchTrackingRequest(BaseModel):
    carrier_code: str
    tracking_number: str
    creds: dict


class TrackingEventItem(BaseModel):
    status: str
    carrier_status: str
    location: str | None = None
    occurred_at: str          # ISO 8601 — datetime serialised as string for transport
    description: str | None = None


class FetchTrackingResponse(BaseModel):
    events: list[TrackingEventItem]


class TestConnectionRequest(BaseModel):
    carrier_code: str
    creds: dict


class CancelInvoiceRequest(BaseModel):
    carrier_code: str
    invoice_id: str
    creds: dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "carrier-gateway"}


@app.get("/supported", dependencies=[Depends(verify_secret)])
def supported() -> dict:
    return {"carrier_codes": list_supported_codes()}


@app.post(
    "/invoke/create-invoice",
    response_model=CreateInvoiceResponse,
    dependencies=[Depends(verify_secret)],
)
def create_invoice(req: CreateInvoiceRequest) -> CreateInvoiceResponse:
    client = get_client(req.carrier_code)
    if client is None:
        raise HTTPException(status_code=422, detail=f"No API client for carrier '{req.carrier_code}'")

    try:
        result = client.create_invoice(req.order_data, req.creds)
    except Exception as exc:
        logger.warning("create_invoice failed: carrier=%s error=%s", req.carrier_code, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    pdf_bytes = result.waybill_pdf_bytes
    if pdf_bytes is None and result.carrier_invoice_id:
        try:
            pdf_bytes = client.get_invoice_pdf(result.carrier_invoice_id, req.creds)
            logger.info(
                "Fetched carrier PDF: carrier=%s invoice=%s size=%d",
                req.carrier_code, result.carrier_invoice_id, len(pdf_bytes),
            )
        except Exception as exc:
            logger.warning(
                "Could not fetch carrier PDF (non-fatal): carrier=%s invoice=%s error=%s",
                req.carrier_code, result.carrier_invoice_id, exc,
            )

    waybill_pdf_b64 = base64.b64encode(pdf_bytes).decode() if pdf_bytes else None
    return CreateInvoiceResponse(
        waybill_number=result.waybill_number,
        carrier_invoice_id=result.carrier_invoice_id,
        waybill_pdf_b64=waybill_pdf_b64,
    )


@app.post(
    "/invoke/fetch-tracking",
    response_model=FetchTrackingResponse,
    dependencies=[Depends(verify_secret)],
)
def fetch_tracking(req: FetchTrackingRequest) -> FetchTrackingResponse:
    adapter = get_adapter(req.carrier_code)
    if adapter is None:
        # Carrier has no polling adapter yet — return empty, not an error
        return FetchTrackingResponse(events=[])

    try:
        events = adapter.fetch_status(req.tracking_number, req.creds)
    except Exception as exc:
        logger.warning(
            "fetch_tracking failed: carrier=%s tracking=%s error=%s",
            req.carrier_code, req.tracking_number, exc,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return FetchTrackingResponse(events=[
        TrackingEventItem(
            status=ev.status,
            carrier_status=ev.carrier_status,
            location=ev.location,
            occurred_at=ev.occurred_at.isoformat(),
            description=ev.description,
        )
        for ev in events
    ])


@app.post("/invoke/test-connection", dependencies=[Depends(verify_secret)])
def test_connection(req: TestConnectionRequest) -> dict:
    client = get_client(req.carrier_code)
    if client is None:
        raise HTTPException(status_code=422, detail=f"No API client for carrier '{req.carrier_code}'")

    try:
        client.test_connection(req.creds)
        return {"ok": True}
    except Exception as exc:
        logger.warning("test_connection failed: carrier=%s error=%s", req.carrier_code, exc)
        return {"ok": False, "error": str(exc)}


@app.post("/invoke/cancel-invoice", dependencies=[Depends(verify_secret)])
def cancel_invoice(req: CancelInvoiceRequest) -> dict:
    client = get_client(req.carrier_code)
    if client is None:
        raise HTTPException(status_code=422, detail=f"No API client for carrier '{req.carrier_code}'")

    try:
        ok = client.cancel_invoice(req.invoice_id, req.creds)
        return {"ok": ok}
    except Exception as exc:
        logger.warning("cancel_invoice failed: carrier=%s error=%s", req.carrier_code, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
