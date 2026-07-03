from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
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
        carrier_payout: Decimal | None = None,
    ) -> Commission:
        c = Commission(
            order_draft_id=order_draft_id,
            carrier_code=carrier_code,
            gross_amount=gross_amount,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            carrier_payout=carrier_payout,
            currency=currency,
        )
        db.add(c)
        db.flush()
        return c

    def delete_for_order(self, db: Session, order_draft_id: int) -> bool:
        c = db.scalar(select(Commission).where(Commission.order_draft_id == order_draft_id))
        if c is None:
            return False
        db.delete(c)
        db.flush()
        return True

    def list_all(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        carrier_code: str | None = None,
    ) -> tuple[Sequence[Commission], int]:
        stmt = select(Commission)
        if date_from:
            stmt = stmt.where(Commission.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Commission.created_at <= date_to)
        if carrier_code:
            stmt = stmt.where(Commission.carrier_code == carrier_code)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(
            stmt.order_by(Commission.created_at.desc()).offset(offset).limit(limit)
        ).all()
        return items, total

    def summary(
        self,
        db: Session,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        carrier_code: str | None = None,
    ) -> dict:
        stmt = select(
            func.coalesce(func.sum(Commission.gross_amount), 0).label("total_gross"),
            func.coalesce(func.sum(Commission.commission_amount), 0).label("total_commission"),
            func.coalesce(
                func.sum(
                    func.coalesce(
                        Commission.carrier_payout,
                        Commission.gross_amount - Commission.commission_amount,
                    )
                ),
                0,
            ).label("total_carrier_payout"),
            func.count(Commission.id).label("count"),
        )
        if date_from:
            stmt = stmt.where(Commission.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Commission.created_at <= date_to)
        if carrier_code:
            stmt = stmt.where(Commission.carrier_code == carrier_code)
        row = db.execute(stmt).one()
        return {
            "total_gross": row.total_gross,
            "total_commission": row.total_commission,
            "total_carrier_payout": row.total_carrier_payout,
            "count": row.count,
        }
