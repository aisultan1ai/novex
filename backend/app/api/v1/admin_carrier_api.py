from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.carriers.api_clients.registry import get_client, list_supported_codes
from app.modules.carriers.api_credentials import (
    CarrierAPICredentialsCreate,
    CarrierAPICredentialsRepository,
    CarrierAPICredentialsResponse,
    CarrierAPICredentialsUpdate,
)

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
    return CarrierAPICredentialsResponse.from_orm_masked(creds)


@router.delete("/{carrier_code}", status_code=204)
def delete_credentials(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> None:
    _repo.delete(db, carrier_code)
    db.commit()
    logger.info("API credentials deleted: carrier_code=%s", carrier_code)


@router.post("/{carrier_code}/test")
def test_connection(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    creds = _repo.get_by_carrier_code(db, carrier_code)
    if not creds:
        raise HTTPException(404, f"API credentials not found for carrier '{carrier_code}'")

    client = get_client(carrier_code)
    if not client:
        raise HTTPException(422, f"No API client implemented for carrier '{carrier_code}'")

    try:
        client.test_connection({
            "api_url": creds.api_url,
            "api_token": creds.api_token,
            **(creds.extra_config or {}),
        })
        logger.info("API connection test success: carrier_code=%s", carrier_code)
        return {"ok": True, "message": "Подключение успешно"}
    except Exception as exc:
        logger.warning("API connection test failed: carrier_code=%s error=%s", carrier_code, exc)
        return {"ok": False, "message": str(exc)}
