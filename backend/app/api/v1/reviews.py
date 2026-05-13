from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import get_current_user_id, require_admin
from app.modules.reviews.schemas import (
    CarrierRatingSummary,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)
from app.modules.reviews.service import ReviewsService

router = APIRouter(tags=["reviews"])
_service = ReviewsService()


@router.post(
    "/orders/{order_draft_id}/review",
    response_model=ReviewResponse,
    status_code=201,
    summary="Оставить отзыв после доставки",
)
def create_review(
    order_draft_id: int,
    payload: ReviewCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    return _service.create_review(
        db,
        user_id=current_user_id,
        order_draft_id=order_draft_id,
        payload=payload,
    )


@router.get(
    "/orders/{order_draft_id}/review",
    response_model=ReviewResponse | None,
    summary="Получить свой отзыв на заказ (null если нет)",
)
def get_my_review(
    order_draft_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewResponse | None:
    return _service.get_my_review(
        db, user_id=current_user_id, order_draft_id=order_draft_id
    )


@router.get(
    "/admin/reviews",
    response_model=ReviewListResponse,
    summary="Список отзывов (только для администратора)",
)
def list_reviews(
    carrier_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> ReviewListResponse:
    return _service.list_reviews(db, carrier_code=carrier_code, page=page, size=size)


@router.get(
    "/admin/reviews/ratings",
    response_model=list[CarrierRatingSummary],
    summary="Средний рейтинг по перевозчикам",
)
def get_ratings_summary(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> list[CarrierRatingSummary]:
    return _service.get_ratings_summary(db)
