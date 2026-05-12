from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.commissions.models import Commission


class CommissionsRepository:
    def create(
        self,
        db: Session,
        *,
        order_draft_id: int,
        carrier_code: str,
        gross_amount: Decimal,
        commission_rate: Decimal,
        commission_amount: Decimal,
        currency: str = "KZT",
    ) -> Commission:
        c = Commission(
            order_draft_id=order_draft_id,
            carrier_code=carrier_code,
            gross_amount=gross_amount,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            currency=currency,
        )
        db.add(c)
        db.flush()
        return c

    def list_all(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Commission], int]:
        total = db.scalar(select(func.count(Commission.id))) or 0
        items = db.scalars(
            select(Commission)
            .order_by(Commission.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return items, total

    def summary(self, db: Session) -> dict:
        row = db.execute(
            select(
                func.coalesce(func.sum(Commission.gross_amount), 0).label("total_gross"),
                func.coalesce(func.sum(Commission.commission_amount), 0).label("total_commission"),
                func.count(Commission.id).label("count"),
            )
        ).one()
        return {
            "total_gross": row.total_gross,
            "total_commission": row.total_commission,
            "count": row.count,
        }
