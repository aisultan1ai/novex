"""
CSE carrier API endpoints.

All endpoints require valid CSE credentials in carrier_api_credentials (code=cse).
They are public-facing helpers used by the frontend to show PVZ maps,
delivery date pickers, and to download waybill PDFs.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin, require_admin_or_operator
from app.core.limiter import limiter
from app.modules.carriers.api_clients.cse import CSEAPIClient
from app.modules.carriers.cse_error_codes import CSEWaybillValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carriers/cse", tags=["cse"])

_client = CSEAPIClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _looks_like_geo_id(value: str) -> bool:
    """True when the input already looks like a CSE geography identifier
    (postcode-KZ-XXXXXX or a GUID). Otherwise treat as a KZ city name."""
    v = value.strip().lower()
    if v.startswith("postcode-"):
        return True
    # GUID: 32 hex chars grouped 8-4-4-4-12.
    import re
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", v))


def _resolve_geo(value: str) -> str:
    """Accept a raw geo identifier or a KZ city name; return a value the CSE
    client can consume (postcode-KZ-XXXXXX for known cities, unchanged
    otherwise). Falls back to the original string when the city is unknown
    so CSE returns its own «not found» error instead of us guessing."""
    if _looks_like_geo_id(value):
        return value
    from app.modules.carriers.cse_geography import city_to_postcode_geo
    resolved = city_to_postcode_geo(value)
    return resolved or value


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
#
# Access model:
#   * Reference lookups (geography, pvz, delivery-*, take-dates) stay public —
#     the shipment form calls them — but are rate-limited because every call
#     spends our CSE credentials.
#   * /waybills/* is staff-only: it exposes recipient PII and DELETE cancels a
#     real waybill at CSE. CSE waybill numbers are sequential, so leaving these
#     open would let anyone enumerate and cancel shipments.

_PUBLIC_RATE_LIMIT = "30/minute"

@router.get("/geography", response_model=list[GeoItem], summary="Search CSE geography")
@limiter.limit(_PUBLIC_RATE_LIMIT)
def search_geography(
    request: Request,
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
@limiter.limit(_PUBLIC_RATE_LIMIT)
def list_pvz(
    request: Request,
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
@limiter.limit(_PUBLIC_RATE_LIMIT)
def delivery_info(
    request: Request,
    from_geo: str = Query(..., description="CSE GUID, postcode-KZ-XXXXXX, or KZ city name"),
    to_geo: str = Query(..., description="CSE GUID, postcode-KZ-XXXXXX, or KZ city name"),
    db: Session = Depends(get_db),
) -> DeliveryInfoResponse:
    """Return transit times and COD/card availability for a route."""
    creds = _get_cse_creds(db)
    from_geo = _resolve_geo(from_geo)
    to_geo = _resolve_geo(to_geo)
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
@limiter.limit(_PUBLIC_RATE_LIMIT)
def available_delivery_dates(
    request: Request,
    from_geo: str = Query(..., description="CSE GUID, postcode-KZ-XXXXXX, or KZ city name (sender)"),
    to_geo: str = Query(..., description="CSE GUID, postcode-KZ-XXXXXX, or KZ city name (recipient)"),
    db: Session = Depends(get_db),
) -> list[AvailableDateItem]:
    """Return available delivery dates and time slots for a route."""
    creds = _get_cse_creds(db)
    from_geo = _resolve_geo(from_geo)
    to_geo = _resolve_geo(to_geo)
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
@limiter.limit(_PUBLIC_RATE_LIMIT)
def available_take_dates(
    request: Request,
    from_geo: str = Query(..., description="CSE GUID, postcode-KZ-XXXXXX, or KZ city name (sender)"),
    db: Session = Depends(get_db),
) -> list[AvailableDateItem]:
    """Return available dates and slots for courier to pick up cargo."""
    creds = _get_cse_creds(db)
    from_geo = _resolve_geo(from_geo)
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
    dependencies=[Depends(require_admin_or_operator)],
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
    dependencies=[Depends(require_admin_or_operator)],
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
    dependencies=[Depends(require_admin_or_operator)],
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
    dependencies=[Depends(require_admin_or_operator)],
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


# ---------------------------------------------------------------------------
# Pickup requests (SaveDocuments)
# ---------------------------------------------------------------------------

class PickupSenderRequest(BaseModel):
    full_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    geography_guid: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    company: str = ""


class PickupRequest(BaseModel):
    sender: PickupSenderRequest
    take_date: str = Field(..., description="YYYY-MM-DD or ISO datetime")
    take_time_from: str = ""
    take_time_to: str = ""
    client_number: str = ""
    comment: str = ""
    waybill_numbers: list[str] = []


class PickupResponse(BaseModel):
    document_number: str


def _raise_cse_error(exc: Exception, method: str) -> None:
    """Translate CSE structured errors to typed HTTP responses.

    422 for validation-level failures (customer can fix); 502 for anything else
    (carrier is broken or unexpected). Preserves the underlying code / hint
    inside detail for support triage.
    """
    if isinstance(exc, CSEWaybillValidationError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.warning("CSE %s failed: %s", method, exc)
    raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc


@router.post(
    "/pickup-requests",
    response_model=PickupResponse,
    summary="Вызвать курьера (SaveDocuments)",
    dependencies=[Depends(require_admin)],
)
def create_pickup_request(
    payload: PickupRequest,
    db: Session = Depends(get_db),
) -> PickupResponse:
    creds = _get_cse_creds(db)
    try:
        document_number = _client.create_pickup_request(
            payload.model_dump(),
            creds,
        )
    except Exception as exc:
        _raise_cse_error(exc, "SaveDocuments")
    return PickupResponse(document_number=document_number)


# ---------------------------------------------------------------------------
# Cargo places (CreateGMH) + dimensions update (UpdateDocuments)
# ---------------------------------------------------------------------------

class CargoPlaceRequest(BaseModel):
    client_code: str = Field(..., min_length=1, description="штрихкод/уникальный код грузоместа")
    weight_kg: float = Field(..., gt=0)
    length_cm: float = 0
    width_cm: float = 0
    height_cm: float = 0
    description: str = ""


class CreateCargoPlacesRequest(BaseModel):
    packages: list[CargoPlaceRequest] = Field(..., min_length=1)


class CreateCargoPlacesResponse(BaseModel):
    guids: list[str]


class UpdateDimensionsRequest(BaseModel):
    packages: list[CargoPlaceRequest] | None = None
    total_weight_kg: float | None = None
    total_volume_weight_kg: float | None = None


@router.post(
    "/waybills/{waybill_number}/cargo-places",
    response_model=CreateCargoPlacesResponse,
    summary="Создать грузоместа (CreateGMH)",
    dependencies=[Depends(require_admin)],
)
def create_cargo_places(
    waybill_number: str,
    payload: CreateCargoPlacesRequest,
    db: Session = Depends(get_db),
) -> CreateCargoPlacesResponse:
    creds = _get_cse_creds(db)
    try:
        guids = _client.create_cargo_places(
            waybill_number,
            [p.model_dump() for p in payload.packages],
            creds,
        )
    except Exception as exc:
        _raise_cse_error(exc, "CreateGMH")
    return CreateCargoPlacesResponse(guids=guids)


@router.patch(
    "/waybills/{waybill_number}/dimensions",
    summary="Обновить ВГХ накладной (UpdateDocuments)",
    dependencies=[Depends(require_admin)],
)
def update_waybill_dimensions(
    waybill_number: str,
    payload: UpdateDimensionsRequest,
    db: Session = Depends(get_db),
) -> dict:
    if not payload.packages and payload.total_weight_kg is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either `packages` or `total_weight_kg`",
        )
    creds = _get_cse_creds(db)
    try:
        _client.update_waybill_dimensions(
            waybill_number,
            creds,
            packages=[p.model_dump() for p in payload.packages] if payload.packages else None,
            total_weight_kg=payload.total_weight_kg,
            total_volume_weight_kg=payload.total_volume_weight_kg,
        )
    except Exception as exc:
        _raise_cse_error(exc, "UpdateDocuments")
    return {"waybill_number": waybill_number, "updated": True}


# ---------------------------------------------------------------------------
# GMH labels (Марка ГМХ 10х9)
# ---------------------------------------------------------------------------

_GMH_FORMAT_MEDIA = {
    "pdf":  ("application/pdf", "pdf"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "xml":  ("application/xml", "xml"),
}


@router.get(
    "/waybills/{waybill_number}/gmh-labels",
    summary="Скачать «Марка ГМХ 10х9»",
    response_class=Response,
    dependencies=[Depends(require_admin)],
)
def download_gmh_labels(
    waybill_number: str,
    fmt: str = Query(default="pdf", pattern="^(pdf|xlsx|xml)$"),
    db: Session = Depends(get_db),
) -> Response:
    creds = _get_cse_creds(db)
    try:
        payload = _client.get_gmh_labels(waybill_number, creds, fmt=fmt)
    except Exception as exc:
        _raise_cse_error(exc, "GetFormsForDocuments (ГМХ)")
    media_type, ext = _GMH_FORMAT_MEDIA[fmt]
    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="cse-gmh-{waybill_number}.{ext}"',
        },
    )


# ---------------------------------------------------------------------------
# Admin-only: reports (Report)
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin/carriers/cse", tags=["cse-admin"])


class ReportResponse(BaseModel):
    report_type: str
    date_from: str
    date_to: str
    rows: list[dict]


@admin_router.get(
    "/reports/{report_type}",
    response_model=ReportResponse,
    summary="Получить отчёт КСЭ",
    dependencies=[Depends(require_admin)],
)
def get_cse_report(
    report_type: str,
    date_from: str = Query(..., description="YYYY-MM-DD"),
    date_to: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> ReportResponse:
    creds = _get_cse_creds(db)
    try:
        rows = _client.get_report(report_type, date_from, date_to, creds)
    except RuntimeError as exc:
        # `unknown report_type` is a client-side validation error — 422.
        msg = str(exc)
        if "unknown report_type" in msg:
            raise HTTPException(status_code=422, detail=msg) from exc
        logger.warning("CSE report failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"CSE API error: {exc}") from exc
    return ReportResponse(
        report_type=report_type,
        date_from=date_from,
        date_to=date_to,
        rows=rows,
    )
