from __future__ import annotations

import logging
import math
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.commissions.repository import CommissionsRepository
from app.modules.commissions.schemas import CommissionResponse, CommissionSummary

logger = logging.getLogger(__name__)

DEFAULT_COMMISSION_RATE = Decimal("0.00")


class CommissionsService:
    def __init__(self, repo: CommissionsRepository | None = None) -> None:
        self.repo = repo or CommissionsRepository()

    def record_commission(
        self,
        db: Session,
        *,
        order_draft_id: int,
        carrier_code: str,
        gross_amount: Decimal,
        currency: str = "KZT",
        rate: Decimal = DEFAULT_COMMISSION_RATE,
    ) -> CommissionResponse:
        commission_amount = (gross_amount * rate).quantize(Decimal("0.01"))
        c = self.repo.create(
            db,
            order_draft_id=order_draft_id,
            carrier_code=carrier_code,
            gross_amount=gross_amount,
            commission_rate=rate,
            commission_amount=commission_amount,
            currency=currency,
        )
        logger.info(
            "Commission recorded: order_id=%s amount=%s rate=%s",
            order_draft_id,
            commission_amount,
            rate,
        )
        return CommissionResponse.model_validate(c)

    def list_commissions(
        self,
        db: Session,
        *,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        offset = (page - 1) * size
        items, total = self.repo.list_all(db, offset=offset, limit=size)
        pages = math.ceil(total / size) if total > 0 else 1
        return {
            "items": [CommissionResponse.model_validate(c) for c in items],
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }

    def get_summary(self, db: Session) -> CommissionSummary:
        data = self.repo.summary(db)
        return CommissionSummary(
            total_gross=Decimal(str(data["total_gross"])),
            total_commission=Decimal(str(data["total_commission"])),
            currency="KZT",
            count=data["count"],
        )
