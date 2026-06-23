from __future__ import annotations

import json
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.carriers.webhook_config import (
    CarrierWebhookCreate,
    CarrierWebhookRepository,
    CarrierWebhookResponse,
    CarrierWebhookUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/carrier-webhooks", tags=["admin:carrier-webhooks"])

_repo = CarrierWebhookRepository()


@router.get("", response_model=list[CarrierWebhookResponse])
def list_carrier_webhooks(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[CarrierWebhookResponse]:
    return [CarrierWebhookResponse.model_validate(c) for c in _repo.list_all(db)]


@router.post("", response_model=CarrierWebhookResponse, status_code=201)
def create_carrier_webhook(
    payload: CarrierWebhookCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CarrierWebhookResponse:
    cfg = _repo.create(db, payload)
    db.commit()
    return CarrierWebhookResponse.model_validate(cfg)


@router.get("/{carrier_code}", response_model=CarrierWebhookResponse)
def get_carrier_webhook(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CarrierWebhookResponse:
    cfg = _repo.get_by_carrier_code(db, carrier_code)
    if cfg is None:
        raise HTTPException(404, "Конфиг не найден")
    return CarrierWebhookResponse.model_validate(cfg)


@router.patch("/{carrier_code}", response_model=CarrierWebhookResponse)
def update_carrier_webhook(
    carrier_code: str,
    payload: CarrierWebhookUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CarrierWebhookResponse:
    try:
        cfg = _repo.update(db, carrier_code, payload)
    except ValueError as err:
        raise HTTPException(404, "Конфиг не найден") from err
    db.commit()
    return CarrierWebhookResponse.model_validate(cfg)


@router.delete("/{carrier_code}", status_code=204)
def delete_carrier_webhook(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> None:
    _repo.delete(db, carrier_code)
    db.commit()


@router.post("/{carrier_code}/test")
def test_carrier_webhook(
    carrier_code: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    cfg = _repo.get_by_carrier_code(db, carrier_code)
    if cfg is None:
        raise HTTPException(404, "Конфиг не найден")
    if not cfg.push_url:
        raise HTTPException(422, "push_url не настроен")

    body = json.dumps({"test": True, "novex_order_id": 0})
    start = time.monotonic()
    try:
        resp = httpx.post(
            cfg.push_url,
            content=body.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Novex-Platform": "novex-logistics",
            },
            timeout=cfg.timeout_seconds,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "status_code": resp.status_code,
            "response_time_ms": elapsed_ms,
            "ok": resp.is_success,
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning("test ping failed for %s: %s", carrier_code, exc)
        return {
            "status_code": None,
            "response_time_ms": None,
            "ok": False,
            "error": str(exc),
        }
