from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.carrier_gateway_client import get_gateway_client
from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.carriers.api_clients.registry import list_supported_codes
from app.modules.carriers.api_credentials import (
    CarrierAPICredentialsCreate,
    CarrierAPICredentialsRepository,
    CarrierAPICredentialsResponse,
    CarrierAPICredentialsUpdate,
)
from app.modules.carriers.creds_cache import invalidate_creds

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/carrier-api", tags=["admin:carrier-api"])
_repo = CarrierAPICredentialsRepository()


@router.get("", response_model=list[CarrierAPICredentialsResponse])
def list_all(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[CarrierAPICredentialsResponse]:
    return [CarrierAPICredentialsResponse.from_orm_masked(c) for c in _repo.list_all(db)]


@router.get("/supported")
def list_supported(_=Depends(require_admin)) -> dict:
    """Список перевозчиков, для которых реализован API-клиент."""
    return {"carrier_codes": list_supported_codes()}


@router.get("/{carrier_code}", response_model=CarrierAPICredentialsResponse)
def get_credentials(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CarrierAPICredentialsResponse:
    creds = _repo.get_by_carrier_code(db, carrier_code)
    if not creds:
        raise HTTPException(404, f"API credentials not found for carrier '{carrier_code}'")
    return CarrierAPICredentialsResponse.from_orm_masked(creds)


@router.post("/{carrier_code}", response_model=CarrierAPICredentialsResponse)
def upsert_credentials(
    carrier_code: str,
    payload: CarrierAPICredentialsCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CarrierAPICredentialsResponse:
    if payload.carrier_code != carrier_code:
        raise HTTPException(422, "carrier_code in body must match URL")
    creds = _repo.upsert(db, payload)
    db.commit()
    db.refresh(creds)
    # Drop the shared Redis cache so live-quote calls, polling and dispatch
    # all pick up the new values on their next request instead of waiting
    # out the TTL (default 5 minutes).
    invalidate_creds(carrier_code)
    logger.info("API credentials upserted: carrier_code=%s", carrier_code)
    return CarrierAPICredentialsResponse.from_orm_masked(creds)


@router.patch("/{carrier_code}", response_model=CarrierAPICredentialsResponse)
def update_credentials(
    carrier_code: str,
    payload: CarrierAPICredentialsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CarrierAPICredentialsResponse:
    try:
        creds = _repo.update(db, carrier_code, payload)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    db.refresh(creds)
    invalidate_creds(carrier_code)
    return CarrierAPICredentialsResponse.from_orm_masked(creds)


@router.delete("/{carrier_code}", status_code=204)
def delete_credentials(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> None:
    _repo.delete(db, carrier_code)
    db.commit()
    invalidate_creds(carrier_code)
    logger.info("API credentials deleted: carrier_code=%s", carrier_code)


@router.get("/azimuth/regions")
def probe_azimuth_regions(
    type: str,
    title: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    """Read-only probe of Azimuth's /regions endpoint.

    Returns the raw JSON body as Azimuth sent it — used to inspect the actual
    response shape before we design a local schema for storing Azimuth city
    mappings. Safe: GET only, no side effects on Azimuth side.

    Usage from admin UI or curl:
        GET /api/v1/admin/carrier-api/azimuth/regions?type=origin&title=Алматы
    """
    from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient

    if type not in ("origin", "destination"):
        raise HTTPException(422, "type must be 'origin' or 'destination'")
    if not title or not title.strip():
        raise HTTPException(422, "title is required")

    creds_obj = _repo.get_by_carrier_code(db, "azimuth")
    if not creds_obj or not creds_obj.is_active:
        raise HTTPException(404, "No active Azimuth API credentials configured")
    creds = {
        "api_url": creds_obj.api_url,
        "api_token": creds_obj.api_token,
        **(creds_obj.extra_config or {}),
    }
    try:
        raw = AzimuthAPIClient().search_regions(type, title, creds)
    except Exception as exc:
        logger.warning("Azimuth regions probe failed: %s", exc)
        raise HTTPException(502, f"Azimuth /regions call failed: {exc}") from exc
    return {"type": type, "title": title, "azimuth_raw_response": raw}


@router.post("/{carrier_code}/test")
def test_connection(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    creds = _repo.get_by_carrier_code(db, carrier_code)
    if not creds:
        raise HTTPException(404, f"API credentials not found for carrier '{carrier_code}'")

    test_creds = {
        "api_url": creds.api_url,
        "api_token": creds.api_token,
        **(creds.extra_config or {}),
    }
    try:
        result = get_gateway_client().test_connection(carrier_code, test_creds)
        if result.get("ok"):
            logger.info("API connection test success: carrier_code=%s", carrier_code)
            return {"ok": True, "message": "Подключение успешно"}
        else:
            logger.warning("API connection test failed: carrier_code=%s error=%s", carrier_code, result.get("error"))
            return {"ok": False, "message": result.get("error", "Ошибка подключения")}
    except Exception as exc:
        logger.warning("Gateway unreachable during test: carrier_code=%s error=%s", carrier_code, exc)
        return {"ok": False, "message": f"Gateway error: {exc}"}
