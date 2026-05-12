from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.notifications.schemas import NotificationListResponse
from app.modules.notifications.service import NotificationsService

router = APIRouter(prefix="/notifications", tags=["notifications"])
_service = NotificationsService()


@router.get("", response_model=NotificationListResponse, summary="Мои уведомления")
def list_notifications(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    return _service.list_notifications(db, user_id=current_user_id)


@router.patch("/{notification_id}/read", status_code=204, summary="Отметить прочитанным")
def mark_read(
    notification_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    _service.mark_read(db, notification_id=notification_id, user_id=current_user_id)


@router.post("/read-all", summary="Отметить все прочитанными")
def mark_all_read(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    count = _service.mark_all_read(db, user_id=current_user_id)
    return {"marked_read": count}
