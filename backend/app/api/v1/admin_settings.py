from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.audit.service import AuditService
from app.modules.identity.models import User
from app.modules.platform_settings.repository import PlatformSettingsRepository

router = APIRouter(prefix="/admin/settings", tags=["admin:settings"])
_repo = PlatformSettingsRepository()
_audit_svc = AuditService()

COMMISSION_RATE_KEY = "commission_rate"
BANK_KEYS = [
    "bank_recipient_name",
    "bank_name",
    "bank_iban",
    "bank_bin",
    "bank_knp",
]


class BankTransferSettings(BaseModel):
    recipient_name: str = ""
    bank_name: str = ""
    iban: str = ""
    bin: str = ""
    knp: str = ""


class PlatformSettingsResponse(BaseModel):
    commission_rate: str
    bank_transfer: BankTransferSettings


class PlatformSettingsUpdate(BaseModel):
    commission_rate: str | None = None
    bank_transfer: BankTransferSettings | None = None


def _load_bank(db: Session) -> BankTransferSettings:
    return BankTransferSettings(
        recipient_name=_repo.get(db, "bank_recipient_name", default="ТОО Novex"),
        bank_name=_repo.get(db, "bank_name", default="Halyk Bank"),
        iban=_repo.get(db, "bank_iban", default=""),
        bin=_repo.get(db, "bank_bin", default=""),
        knp=_repo.get(db, "bank_knp", default="710"),
    )


@router.get("", response_model=PlatformSettingsResponse, summary="Настройки платформы")
def get_settings(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> PlatformSettingsResponse:
    rate = _repo.get(db, COMMISSION_RATE_KEY, default="0.00")
    return PlatformSettingsResponse(commission_rate=rate, bank_transfer=_load_bank(db))


@router.patch("", response_model=PlatformSettingsResponse, summary="Обновить настройки")
def update_settings(
    payload: PlatformSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PlatformSettingsResponse:
    if payload.commission_rate is not None:
        try:
            rate = Decimal(payload.commission_rate)
        except InvalidOperation as err:
            raise HTTPException(status_code=422, detail="commission_rate должен быть числом") from err
        if not (Decimal("0") <= rate <= Decimal("1")):
            raise HTTPException(status_code=422, detail="commission_rate должен быть от 0 до 1")
        _repo.set(db, COMMISSION_RATE_KEY, str(rate.quantize(Decimal("0.0001"))))

    if payload.bank_transfer is not None:
        bt = payload.bank_transfer
        _repo.set(db, "bank_recipient_name", bt.recipient_name.strip())
        _repo.set(db, "bank_name", bt.bank_name.strip())
        _repo.set(db, "bank_iban", bt.iban.strip())
        _repo.set(db, "bank_bin", bt.bin.strip())
        _repo.set(db, "bank_knp", bt.knp.strip())

    db.commit()
    _audit_svc.log(
        db,
        actor=admin,
        action="settings.update",
        resource_type="settings",
        new_value=payload.model_dump(exclude_none=True),
    )
    db.commit()
    current_rate: str = _repo.get(db, COMMISSION_RATE_KEY, default="0.00")
    return PlatformSettingsResponse(commission_rate=current_rate, bank_transfer=_load_bank(db))
