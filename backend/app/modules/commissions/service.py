from __future__ import annotations

import logging
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.carriers.models import CarrierCommissionConfig
from app.modules.commissions.repository import CommissionsRepository
from app.modules.commissions.schemas import CommissionResponse, CommissionSummary
from app.modules.platform_settings.repository import PlatformSettingsRepository

logger = logging.getLogger(__name__)

DEFAULT_COMMISSION_RATE = Decimal("0.00")
_settings_repo = PlatformSettingsRepository()


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
        precomputed_markup: Decimal | None = None,
        carrier_payout: Decimal | None = None,
    ) -> CommissionResponse:
        """Persist a commission row for an order that just got paid.

        `precomputed_markup` — the markup already stored on the order at quote
        time. When provided we skip re-reading commission configs and just
        record the exact amounts the customer was quoted. This prevents drift
        if admin edits the rate between quote and payment.
        `carrier_payout` — what perevozchik receives (gross_amount - markup).
        """
        if precomputed_markup is not None:
            commission_amount = Decimal(str(precomputed_markup)).quantize(Decimal("0.01"))
            effective_rate = (
                (commission_amount / gross_amount).quantize(Decimal("0.0001"))
                if gross_amount and gross_amount > 0 else Decimal("0")
            )
        else:
            # Fallback path: order predates markup capture (migration 032) or
            # caller didn't supply it. Recompute from live config.
            config = db.scalar(
                select(CarrierCommissionConfig).where(
                    CarrierCommissionConfig.carrier_code == carrier_code
                )
            )

            if config is not None:
                commission_amount = self._calculate(
                    gross_amount=gross_amount,
                    commission_type=config.commission_type,
                    commission_rate=Decimal(str(config.commission_rate))
                    if config.commission_rate
                    else Decimal("0"),
                    fixed_amount=Decimal(str(config.fixed_amount))
                    if config.fixed_amount
                    else Decimal("0"),
                )
                effective_rate = (
                    Decimal(str(config.commission_rate))
                    if config.commission_rate
                    else Decimal("0")
                )
            else:
                global_rate_raw = _settings_repo.get(db, "commission_rate", default="")
                if global_rate_raw:
                    try:
                        effective_rate = Decimal(global_rate_raw)
                    except InvalidOperation:
                        logger.warning(
                            "Invalid global commission_rate value '%s'; using 0", global_rate_raw
                        )
                        effective_rate = rate
                else:
                    effective_rate = rate
                if effective_rate == Decimal("0"):
                    logger.warning(
                        "Commission recorded with rate=0 for carrier '%s' order_id=%s — "
                        "configure a CarrierCommissionConfig or set the global 'commission_rate' "
                        "in platform settings.",
                        carrier_code,
                        order_draft_id,
                    )
                commission_amount = (gross_amount * effective_rate).quantize(Decimal("0.01"))

        # Default carrier_payout so the payouts view has no NULLs on new rows.
        if carrier_payout is None:
            carrier_payout = (gross_amount - commission_amount).quantize(Decimal("0.01"))

        c = self.repo.create(
            db,
            order_draft_id=order_draft_id,
            carrier_code=carrier_code,
            gross_amount=gross_amount,
            commission_rate=effective_rate,
            commission_amount=commission_amount,
            currency=currency,
            carrier_payout=carrier_payout,
        )
        logger.info(
            "Commission recorded: order_id=%s payout=%s profit=%s carrier=%s",
            order_draft_id,
            carrier_payout,
            commission_amount,
            carrier_code,
        )
        return CommissionResponse.model_validate(c)

    def void_for_order(self, db: Session, order_draft_id: int) -> bool:
        deleted = self.repo.delete_for_order(db, order_draft_id)
        if deleted:
            logger.info("Commission voided on refund: order_id=%s", order_draft_id)
        return deleted

    def _calculate(
        self,
        *,
        gross_amount: Decimal,
        commission_type: str,
        commission_rate: Decimal,
        fixed_amount: Decimal,
    ) -> Decimal:
        if commission_type == "percentage":
            return (gross_amount * commission_rate).quantize(Decimal("0.01"))
        if commission_type == "fixed":
            return fixed_amount.quantize(Decimal("0.01"))
        # combined
        return (gross_amount * commission_rate + fixed_amount).quantize(Decimal("0.01"))

    def list_commissions(
        self,
        db: Session,
        *,
        page: int = 1,
        size: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        carrier_code: str | None = None,
    ) -> dict:
        offset = (page - 1) * size
        items, total = self.repo.list_all(
            db,
            offset=offset,
            limit=size,
            date_from=date_from,
            date_to=date_to,
            carrier_code=carrier_code,
        )
        pages = math.ceil(total / size) if total > 0 else 1
        return {
            "items": [CommissionResponse.model_validate(c) for c in items],
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }

    def get_summary(
        self,
        db: Session,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        carrier_code: str | None = None,
    ) -> CommissionSummary:
        data = self.repo.summary(db, date_from=date_from, date_to=date_to, carrier_code=carrier_code)
        return CommissionSummary(
            total_gross=Decimal(str(data["total_gross"])),
            total_carrier_payout=Decimal(str(data["total_carrier_payout"])),
            total_commission=Decimal(str(data["total_commission"])),
            currency="KZT",
            count=data["count"],
        )
