from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin
from app.modules.commissions.schemas import CommissionSummary
from app.modules.commissions.service import CommissionsService

router = APIRouter(prefix="/admin/commissions", tags=["admin:commissions"])
_service = CommissionsService()


@router.get("", summary="Список комиссий")
def list_commissions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> dict:
    return _service.list_commissions(
        db,
        page=page,
        size=size,
        date_from=date_from,
        date_to=date_to,
        carrier_code=carrier_code,
    )


@router.get("/summary", response_model=CommissionSummary, summary="Итоги по комиссиям")
def commissions_summary(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> CommissionSummary:
    return _service.get_summary(db, date_from=date_from, date_to=date_to, carrier_code=carrier_code)
