from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.reviews.models import Review


class ReviewsRepository:
    def create(
        self,
        db: Session,
        *,
        order_draft_id: int,
        user_id: int,
        carrier_code: str,
        rating: int,
        comment: str | None,
    ) -> Review:
        review = Review(
            order_draft_id=order_draft_id,
            user_id=user_id,
            carrier_code=carrier_code,
            rating=rating,
            comment=comment,
        )
        db.add(review)
        db.flush()
        return review

    def get_by_order_id(self, db: Session, order_draft_id: int) -> Review | None:
        return db.scalar(
            select(Review).where(Review.order_draft_id == order_draft_id)
        )

    def list_for_admin(
        self,
        db: Session,
        *,
        carrier_code: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Review], int]:
        stmt = select(Review).order_by(Review.created_at.desc())
        if carrier_code:
            stmt = stmt.where(Review.carrier_code == carrier_code)
        total: int = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(db.scalars(stmt.offset(offset).limit(limit)).all())
        return items, total

    def avg_rating_by_carrier(self, db: Session) -> list[dict]:
        rows = db.execute(
            select(
                Review.carrier_code,
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("count"),
            ).group_by(Review.carrier_code)
        ).all()
        return [
            {
                "carrier_code": r.carrier_code,
                "avg_rating": float(r.avg_rating),
                "count": r.count,
            }
            for r in rows
        ]
