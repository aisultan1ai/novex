from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.modules.carriers.tariff_engine import (
    calculate_quotes_async as _engine_quotes_async,
)
from app.modules.quotes.models import QuoteSession, RateQuote
from app.modules.quotes.schemas import (
    CarrierServiceItem,
    QuoteSelectionRequest,
    RateQuoteItem,
    ShippingQuoteRequest,
    ShippingQuoteResponse,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

_TOKEN_TTL_HOURS = 24

logger = logging.getLogger(__name__)


class QuotesService:
    async def calculate_quotes(
        self,
        db: AsyncSession,
        payload: ShippingQuoteRequest,
    ) -> ShippingQuoteResponse:
        quotes = await _engine_quotes_async(
            from_city=payload.from_city,
            to_city=payload.to_city,
            weight_kg=float(payload.weight_kg),
            quantity=int(payload.quantity),
            width_cm=float(payload.width_cm),
            height_cm=float(payload.height_cm),
            depth_cm=float(payload.depth_cm),
            db=db,
            shipment_type=payload.shipment_type,
        )

        quote_session = QuoteSession(
            from_country=payload.from_country,
            from_city=payload.from_city,
            to_country=payload.to_country,
            to_city=payload.to_city,
            weight_kg=Decimal(str(payload.weight_kg)),
            quantity=payload.quantity,
            width_cm=Decimal(str(payload.width_cm)),
            height_cm=Decimal(str(payload.height_cm)),
            depth_cm=Decimal(str(payload.depth_cm)),
            shipment_type=payload.shipment_type,
            public_token=secrets.token_urlsafe(32),
            expires_at=_utcnow() + timedelta(hours=_TOKEN_TTL_HOURS),
        )
        db.add(quote_session)
        await db.flush()

        cheapest = min(quotes, key=lambda q: q.price, default=None)
        fastest_quote = min(quotes, key=lambda q: q.eta_days_min, default=None)

        rate_rows: list[RateQuote] = []
        for q in quotes:
            badge = None
            if cheapest and q.tariff_code == cheapest.tariff_code:
                badge = "best_value"
            elif fastest_quote and q.tariff_code == fastest_quote.tariff_code:
                badge = "fastest"

            rq = RateQuote(
                quote_session_id=quote_session.id,
                carrier_code=q.carrier_code,
                carrier_name=q.carrier_name,
                tariff_name=q.tariff_name,
                price=q.price,
                currency=q.currency,
                eta_days_min=q.eta_days_min,
                eta_days_max=q.eta_days_max,
                badge=badge,
                urgency_guid=q.urgency_guid,
            )
            rate_rows.append(rq)

        db.add_all(rate_rows)
        await db.commit()
        await db.refresh(quote_session)

        logger.info(
            "Quotes calculated: session_id=%s from=%s/%s to=%s/%s quotes=%s",
            quote_session.id,
            payload.from_country,
            payload.from_city,
            payload.to_country,
            payload.to_city,
            len(rate_rows),
        )
        return ShippingQuoteResponse(
            quote_session_id=quote_session.id,
            public_token=quote_session.public_token,
            quotes=[
                self._to_item(rq, q.available_services)
                for rq, q in zip(rate_rows, quotes)
            ],
        )

    def get_quote_session(
        self,
        db: Session,
        session_id: int,
    ) -> ShippingQuoteResponse:
        stmt = (
            select(QuoteSession)
            .where(QuoteSession.id == session_id)
            .options(selectinload(QuoteSession.rate_quotes))
        )
        session = db.scalar(stmt)
        if not session:
            logger.warning("Quote session not found: session_id=%s", session_id)
            raise NotFoundError("Quote session not found.")

        return ShippingQuoteResponse(
            quote_session_id=session.id,
            quotes=[self._to_item(r) for r in session.rate_quotes],
        )

    def select_quote(
        self,
        db: Session,
        quote_session_id: int,
        payload: QuoteSelectionRequest,
    ) -> ShippingQuoteResponse:
        # Lock the target row first to prevent concurrent double-selection
        rate = db.scalar(
            select(RateQuote)
            .where(
                RateQuote.quote_session_id == quote_session_id,
                RateQuote.id == payload.rate_quote_id,
            )
            .with_for_update()
        )
        if not rate:
            logger.warning(
                "Rate quote not found: session_id=%s rate_quote_id=%s",
                quote_session_id,
                payload.rate_quote_id,
            )
            raise NotFoundError("Rate quote not found.")

        db.execute(
            update(RateQuote)
            .where(
                RateQuote.quote_session_id == quote_session_id,
                RateQuote.is_selected.is_(True),
            )
            .values(is_selected=False)
        )

        rate.is_selected = True
        db.commit()

        logger.info(
            "Rate quote selected: session_id=%s rate_quote_id=%s carrier=%s",
            quote_session_id,
            rate.id,
            rate.carrier_code,
        )
        return self.get_quote_session(db, quote_session_id)

    @staticmethod
    def _to_item(rq: RateQuote, services: list[dict] | None = None) -> RateQuoteItem:
        svc_items = [CarrierServiceItem(**s) for s in (services or [])]
        return RateQuoteItem(
            id=rq.id,
            carrier_code=rq.carrier_code,
            carrier_name=rq.carrier_name,
            tariff_name=rq.tariff_name,
            price=rq.price,
            currency=rq.currency,
            eta_days_min=rq.eta_days_min,
            eta_days_max=rq.eta_days_max,
            badge=rq.badge,
            is_selected=rq.is_selected,
            available_services=svc_items,
        )
