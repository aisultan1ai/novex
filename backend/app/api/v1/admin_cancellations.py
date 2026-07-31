"""Admin endpoints for cancellation requests.

Все методы за require_admin_or_operator (уровень 'operator' достаточен для
принятия решений по заявкам — это операционная работа, не финансовая).
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import require_admin_or_operator
from app.modules.cancellations.repository import CancellationRequestsRepository
from app.modules.cancellations.schemas import (
    CancellationRequestListResponse,
    CancellationRequestResolve,
    CancellationRequestResponse,
)
from app.modules.cancellations.service import CancellationRequestsService
from app.modules.identity.models import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/cancellation-requests",
    tags=["admin:cancellations"],
)

_repo = CancellationRequestsRepository()
_service = CancellationRequestsService()


@router.get("", response_model=CancellationRequestListResponse)
def list_requests(
    status: str | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_operator),
) -> CancellationRequestListResponse:
    items, total = _repo.list_paginated(
        db,
        offset=(page - 1) * size,
        limit=size,
        status=status,
        carrier_code=carrier_code,
    )
    pages = math.ceil(total / size) if total > 0 else 1
    return CancellationRequestListResponse(
        items=[CancellationRequestResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{request_id}", response_model=CancellationRequestResponse)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_operator),
) -> CancellationRequestResponse:
    from app.core.exceptions import NotFoundError

    req = _repo.get(db, request_id)
    if req is None:
        raise NotFoundError("Заявка на отмену не найдена")
    return CancellationRequestResponse.model_validate(req)


@router.post("/{request_id}/approve", response_model=CancellationRequestResponse)
def approve_request(
    request_id: int,
    payload: CancellationRequestResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_operator),
) -> CancellationRequestResponse:
    return _service.approve_by_admin(
        db,
        request_id=request_id,
        admin_id=current_user.id,
        comment=payload.comment,
    )


@router.post("/{request_id}/reject", response_model=CancellationRequestResponse)
def reject_request(
    request_id: int,
    payload: CancellationRequestResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_operator),
) -> CancellationRequestResponse:
    # На rejection комментарий обязателен — сервис сам валидирует минимум 3
    # символа. Здесь только прокидываем строку (comment=None → 422 в сервисе).
    return _service.reject(
        db,
        request_id=request_id,
        actor_user_id=current_user.id,
        actor_is_admin=True,
        actor_carrier_code=None,
        comment=payload.comment or "",
    )


@router.post("/{request_id}/retry-api", response_model=CancellationRequestResponse)
def retry_api(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_operator),
) -> CancellationRequestResponse:
    return _service.retry_api_cancel(
        db,
        request_id=request_id,
        admin_id=current_user.id,
    )
