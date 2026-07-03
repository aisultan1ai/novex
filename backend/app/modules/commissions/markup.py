"""Markup / commission calculation for quotes.

Given a carrier-side price, compute how much Novex adds on top before showing
the amount to the customer. Uses per-carrier CarrierCommissionConfig if
present, otherwise the platform-wide default from platform_settings. Per-carrier
config REPLACES the global rate (they do not stack) — matches the product
requirement: if any carrier has a config, others still fall back to the global.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.modules.carriers.models import CarrierCommissionConfig
from app.modules.platform_settings.repository import PlatformSettingsRepository

logger = logging.getLogger(__name__)

_settings_repo = PlatformSettingsRepository()
_ZERO = Decimal("0.00")
_CENT = Decimal("0.01")


class MarkupCalculator:
    """Resolves markup for carriers from DB config; caches configs per instance.

    Not thread-safe — construct fresh per request / job, since the config table
    can change between calls (admin edits rate).
    """

    def __init__(
        self,
        per_carrier: dict[str, CarrierCommissionConfig],
        global_rate: Decimal,
    ) -> None:
        self._per_carrier = per_carrier
        self._global_rate = global_rate

    def markup_for(self, carrier_code: str, carrier_price: Decimal) -> Decimal:
        """Compute the markup amount for a single line.

        The returned value is the amount ADDED to carrier_price before showing
        the customer; commission_amount stored on order equals this value.
        """
        config = self._per_carrier.get(carrier_code)
        if config is None:
            # No per-carrier config → global rate applies. If global is 0 the
            # customer pays the carrier price verbatim (backwards compatible).
            return (carrier_price * self._global_rate).quantize(_CENT)

        rate = Decimal(str(config.commission_rate)) if config.commission_rate is not None else _ZERO
        fixed = Decimal(str(config.fixed_amount)) if config.fixed_amount is not None else _ZERO

        if config.commission_type == "percentage":
            return (carrier_price * rate).quantize(_CENT)
        if config.commission_type == "fixed":
            return fixed.quantize(_CENT)
        if config.commission_type == "combined":
            return (carrier_price * rate + fixed).quantize(_CENT)

        logger.warning(
            "Unknown commission_type=%s for carrier=%s; falling back to 0 markup",
            config.commission_type, carrier_code,
        )
        return _ZERO


def _read_global_rate(raw: str | None) -> Decimal:
    if not raw:
        return _ZERO
    try:
        return Decimal(raw)
    except InvalidOperation:
        logger.warning("Invalid platform commission_rate '%s'; treating as 0", raw)
        return _ZERO


def build_markup_calculator(db: Session, carrier_codes: Iterable[str]) -> MarkupCalculator:
    """Load configs for the given carriers + the global fallback in one shot."""
    codes = list({c for c in carrier_codes if c})
    per_carrier: dict[str, CarrierCommissionConfig] = {}
    if codes:
        rows = db.scalars(
            select(CarrierCommissionConfig).where(
                CarrierCommissionConfig.carrier_code.in_(codes)
            )
        ).all()
        per_carrier = {r.carrier_code: r for r in rows}

    global_rate = _read_global_rate(_settings_repo.get(db, "commission_rate", default=""))
    return MarkupCalculator(per_carrier=per_carrier, global_rate=global_rate)


async def build_markup_calculator_async(
    db: AsyncSession, carrier_codes: Iterable[str]
) -> MarkupCalculator:
    codes = list({c for c in carrier_codes if c})
    per_carrier: dict[str, CarrierCommissionConfig] = {}
    if codes:
        result = await db.execute(
            select(CarrierCommissionConfig).where(
                CarrierCommissionConfig.carrier_code.in_(codes)
            )
        )
        rows = result.scalars().all()
        per_carrier = {r.carrier_code: r for r in rows}

    # PlatformSettingsRepository.get() uses db.scalar() which does not support
    # AsyncSession; query directly. Redis cache is still hit first via lookup.
    raw_rate: str = ""
    try:
        from app.core.redis import get_redis
        cached = get_redis().get("pset:commission_rate")
        if cached is not None:
            raw_rate = cached if isinstance(cached, str) else cached.decode()  # type: ignore[union-attr]
    except Exception:
        pass
    if not raw_rate:
        from app.modules.platform_settings.models import PlatformSetting
        row = (await db.execute(
            select(PlatformSetting).where(PlatformSetting.key == "commission_rate")
        )).scalar_one_or_none()
        raw_rate = row.value if row else ""

    return MarkupCalculator(per_carrier=per_carrier, global_rate=_read_global_rate(raw_rate))
