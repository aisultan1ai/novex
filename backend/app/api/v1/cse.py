"""
CSE carrier API endpoints.

All endpoints require valid CSE credentials in carrier_api_credentials (code=cse).
They are public-facing helpers used by the frontend to show PVZ maps,
delivery date pickers, and to download waybill PDFs.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.carriers.api_clients.cse import CSEAPIClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carriers/cse", tags=["cse"])

_client = CSEAPIClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cse_creds(db: Session) -> dict:
    """Load CSE credentials from DB. Raises 503 if not configured."""
    from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
    repo = CarrierAPICredentialsRepository()
    record = repo.get_by_carrier_code(db, "cse")
    if not record or not record.is_active:
        raise HTTPException(status_code=503, detail="CSE carrier is not configured")
    creds = {
        "api_url": record.api_url or "",
        "api_token": record.api_token or "",
    }
    if record.extra_config:
        creds.update(record.extra_config)
    return creds


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GeoItem(BaseModel):
    guid: str
    name: str
    parent: str
    type: str
    fias: str
    iata: str


class PvzItem(BaseModel):
    guid: str
    address: str
    city: str
    lat: str
    lon: str
    schedule: str
    phone: str
    type: str


class DeliveryInfoResponse(BaseModel):
    min_days: int | None
    max_days: int | None
    cod_available: bool
    card_available: bool
    services: list[dict]


class AvailableDateItem(BaseModel):
    date: str
    time_from: str
    time_to: str
    slots: list[dict]


class WaybillInfo(BaseModel):
    number: str
    status: str
    sender: str
    recipient: str
    weight: float | None
    created_at: str


class TrackingEvent(BaseModel):
    guid: str
    status: str
    occurred_at: str
    location: str
    comment: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/geography", response_model=list[GeoItem], summary="Search CSE geography")
def search_geography(
    search: str = Query(..., min_length=2, description="City name, postal code, or FIAS"),
    db: Session = Depends(get_db),
) -> list[GeoItem]:
    """Search CSE Geography reference directory."""
    creds = _get_cse_creds(db)
    try:
        results = _client.search_geography(search, creds)
    except Exception as exc:
        logger.warning("CSE geography search failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return [GeoItem(**r) for r in results]


@router.get("/pvz", response_model=list[PvzItem], summary="List CSE pickup/delivery points")
def list_pvz(
    city_guid: str | None = Query(default=None, description="Filter by CSE city GUID"),
    city: str | None = Query(
        default=None,
        description="City name; server resolves it to a GUID (ignored if city_guid is given)",
    ),
    db: Session = Depends(get_db),
) -> list[PvzItem]:
    """Return CSE pickup/delivery points, optionally filtered by city.

    Accepts either the raw city GUID or a city name (server does the geography
    lookup and reuses the Redis GUID cache). If both are given, `city_guid`
    wins.
    """
    creds = _get_cse_creds(db)

    resolved_guid = city_guid
    if not resolved_guid and city:
        from app.modules.carriers.cse_geography import get_city_guid
        resolved_guid = get_city_guid(city, creds)
        if not resolved_guid:
            # Unknown city — return empty list rather than surfacing all PVZs
            # (which would let the UI silently pick a PVZ in the wrong city).
            return []

    try:
        results = _client.get_pvz(creds, geography_guid=resolved_guid)
    except Exception as exc:
        logger.warning("CSE pvz list failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return [PvzItem(**r) for r in results]


@router.get(
    "/delivery-info",
    response_model=DeliveryInfoResponse,
    summary="Get delivery info for a route",
)
def delivery_info(
    from_geo: str = Query(..., description="CSE geography GUID or postcode-KZ-XXXXXX"),
    to_geo: str = Query(..., description="CSE geography GUID or postcode-KZ-XXXXXX"),
    db: Session = Depends(get_db),
) -> DeliveryInfoResponse:
    """Return transit times and COD/card availability for a route."""
    creds = _get_cse_creds(db)
    try:
        info = _client.get_delivery_info(from_geo, to_geo, creds)
    except Exception as exc:
        logger.warning("CSE delivery_info failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return DeliveryInfoResponse(**info)


@router.get(
    "/delivery-dates",
    response_model=list[AvailableDateItem],
    summary="Available delivery date/time slots",
)
def available_delivery_dates(
    from_geo: str = Query(..., description="CSE geography GUID or postcode-KZ-XXXXXX of sender"),
    to_geo: str = Query(..., description="CSE geography GUID or postcode-KZ-XXXXXX of recipient"),
    db: Session = Depends(get_db),
) -> list[AvailableDateItem]:
    """Return available delivery dates and time slots for a route."""
    creds = _get_cse_creds(db)
    try:
        results = _client.get_available_delivery_dates(from_geo, to_geo, creds)
    except Exception as exc:
        logger.warning("CSE delivery dates failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return [AvailableDateItem(**r) for r in results]


@router.get(
    "/take-dates",
    response_model=list[AvailableDateItem],
    summary="Available courier pickup date/time slots",
)
def available_take_dates(
    from_geo: str = Query(..., description="CSE geography GUID or postcode-KZ-XXXXXX of sender"),
    db: Session = Depends(get_db),
) -> list[AvailableDateItem]:
    """Return available dates and slots for courier to pick up cargo."""
    creds = _get_cse_creds(db)
    try:
        results = _client.get_available_take_dates(from_geo, creds)
    except Exception as exc:
        logger.warning("CSE take dates failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return [AvailableDateItem(**r) for r in results]


@router.get(
    "/waybills/{waybill_number}",
    response_model=WaybillInfo,
    summary="Get waybill data",
)
def get_waybill(
    waybill_number: str,
    db: Session = Depends(get_db),
) -> WaybillInfo:
    """Fetch full data for a CSE waybill."""
    creds = _get_cse_creds(db)
    try:
        data = _client.get_documents(waybill_number, creds)
    except Exception as exc:
        logger.warning("CSE get_documents failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    w = data.get("weight")
    return WaybillInfo(
        number=data.get("number", waybill_number),
        status=data.get("status", ""),
        sender=data.get("sender", ""),
        recipient=data.get("recipient", ""),
        weight=float(w) if w is not None else None,
        created_at=data.get("created_at", ""),
    )


@router.get(
    "/waybills/{waybill_number}/tracking",
    response_model=list[TrackingEvent],
    summary="Get waybill tracking history",
)
def get_tracking(
    waybill_number: str,
    db: Session = Depends(get_db),
) -> list[TrackingEvent]:
    """Return status event history for a CSE waybill."""
    creds = _get_cse_creds(db)
    try:
        events = _client.tracking(waybill_number, creds)
    except Exception as exc:
        logger.warning("CSE tracking failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return [
        TrackingEvent(
            guid=ev.get("guid", ""),
            status=ev.get("status", ""),
            occurred_at=str(ev.get("occurred_at", "")),
            location=ev.get("location", ""),
            comment=ev.get("comment", ""),
        )
        for ev in events
    ]


@router.get(
    "/waybills/{waybill_number}/pdf",
    summary="Download waybill PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF waybill"}},
)
def download_waybill_pdf(
    waybill_number: str,
    db: Session = Depends(get_db),
) -> Response:
    """Download print form (PDF) of a CSE waybill."""
    creds = _get_cse_creds(db)
    try:
        pdf_bytes = _client.get_print_form(waybill_number, creds)
    except Exception as exc:
        logger.warning("CSE print form failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cse-{waybill_number}.pdf"',
        },
    )


@router.delete(
    "/waybills/{waybill_number}",
    summary="Cancel a CSE waybill",
)
def cancel_waybill(
    waybill_number: str,
    reason: str = Query(..., description="Cancellation reason"),
    contact: str = Query(..., description="Contact person name"),
    phone: str = Query(..., description="Contact phone"),
    db: Session = Depends(get_db),
) -> dict:
    """Cancel a CSE waybill by number."""
    creds = _get_cse_creds(db)
    success = _client.delete_document(waybill_number, reason, contact, phone, creds)
    if not success:
        raise HTTPException(status_code=502, detail="CSE: cancellation request failed")
    return {"waybill_number": waybill_number, "cancelled": True}
