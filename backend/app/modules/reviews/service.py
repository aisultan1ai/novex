from __future__ import annotations

import logging
import math

from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.orders.repository import OrdersRepository
from app.modules.reviews.repository import ReviewsRepository
from app.modules.reviews.schemas import (
    CarrierRatingSummary,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)

logger = logging.getLogger(__name__)

_REVIEWABLE_STATUSES = {"delivered", "return", "returned"}


class ReviewsService:
    def __init__(
        self,
        repo: ReviewsRepository | None = None,
        orders_repo: OrdersRepository | None = None,
    ) -> None:
        self.repo = repo or ReviewsRepository()
        self.orders_repo = orders_repo or OrdersRepository()

    def create_review(
        self,
        db: Session,
        *,
        user_id: int,
        order_draft_id: int,
        payload: ReviewCreate,
    ) -> ReviewResponse:
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Нет доступа к этому заказу")
        if order.status not in _REVIEWABLE_STATUSES:
            raise ValidationError(
                f"Отзыв можно оставить только после доставки. "
                f"Текущий статус: {order.status}"
            )

        existing = self.repo.get_by_order_id(db, order_draft_id)
        if existing is not None:
            raise ConflictError("Отзыв на этот заказ уже существует")

        review = self.repo.create(
            db,
            order_draft_id=order_draft_id,
            user_id=user_id,
            carrier_code=order.carrier_code_snapshot,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.commit()
        logger.info(
            "Review created: order_id=%s user_id=%s rating=%s",
            order_draft_id,
            user_id,
            payload.rating,
        )
        return ReviewResponse.model_validate(review)

    def get_my_review(
        self,
        db: Session,
        *,
        user_id: int,
        order_draft_id: int,
    ) -> ReviewResponse | None:
        order = self.orders_repo.get_order_draft_by_id(db, order_draft_id)
        if order is None:
            raise NotFoundError("Заказ не найден")
        if order.user_id != user_id:
            raise ForbiddenError("Нет доступа к этому заказу")
        existing = self.repo.get_by_order_id(db, order_draft_id)
        if existing is None:
            return None
        return ReviewResponse.model_validate(existing)

    def list_reviews(
        self,
        db: Session,
        *,
        carrier_code: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> ReviewListResponse:
        offset = (page - 1) * size
        items, total = self.repo.list_for_admin(
            db, carrier_code=carrier_code, offset=offset, limit=size
        )
        pages = math.ceil(total / size) if total > 0 else 1
        return ReviewListResponse(
            items=[ReviewResponse.model_validate(r) for r in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    def get_ratings_summary(self, db: Session) -> list[CarrierRatingSummary]:
        rows = self.repo.avg_rating_by_carrier(db)
        return [CarrierRatingSummary(**r) for r in rows]
