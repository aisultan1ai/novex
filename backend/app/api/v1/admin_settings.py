from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.platform_settings.repository import PlatformSettingsRepository

router = APIRouter(prefix="/admin/settings", tags=["admin:settings"])
_repo = PlatformSettingsRepository()

COMMISSION_RATE_KEY = "commission_rate"


class PlatformSettingsResponse(BaseModel):
    commission_rate: str


class PlatformSettingsUpdate(BaseModel):
    commission_rate: str


@router.get("", response_model=PlatformSettingsResponse, summary="Настройки платформы")
def get_settings(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> PlatformSettingsResponse:
    rate = _repo.get(db, COMMISSION_RATE_KEY, default="0.00")
    return PlatformSettingsResponse(commission_rate=rate)


@router.patch("", response_model=PlatformSettingsResponse, summary="Обновить настройки")
def update_settings(
    payload: PlatformSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> PlatformSettingsResponse:
    try:
        rate = Decimal(payload.commission_rate)
    except InvalidOperation as err:
        raise HTTPException(
            status_code=422, detail="commission_rate должен быть числом"
        ) from err

    if not (Decimal("0") <= rate <= Decimal("1")):
        raise HTTPException(
            status_code=422, detail="commission_rate должен быть от 0 до 1"
        )

    rate_str = str(rate.quantize(Decimal("0.0001")))
    _repo.set(db, COMMISSION_RATE_KEY, rate_str)
    db.commit()
    return PlatformSettingsResponse(commission_rate=rate_str)
