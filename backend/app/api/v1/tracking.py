from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id, require_admin
from app.modules.tracking.schemas import (
    TrackingEventCreate,
    TrackingEventResponse,
    TrackingHistoryResponse,
)
from app.modules.tracking.service import TrackingService

router = APIRouter(prefix="/orders", tags=["tracking"])
_service = TrackingService()


@router.get(
    "/{draft_id}/tracking",
    response_model=TrackingHistoryResponse,
    summary="История трекинга заказа",
)
def get_order_tracking(
    draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TrackingHistoryResponse:
    return _service.get_tracking(db, user_id=current_user_id, order_draft_id=draft_id)


@router.post(
    "/{draft_id}/tracking",
    response_model=TrackingEventResponse,
    status_code=201,
    summary="Добавить событие трекинга (admin)",
)
def add_tracking_event(
    draft_id: int,
    payload: TrackingEventCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> TrackingEventResponse:
    return _service.add_event(db, order_draft_id=draft_id, payload=payload)
