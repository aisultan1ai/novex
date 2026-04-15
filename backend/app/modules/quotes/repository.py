from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.quotes.models import QuoteSession, RateQuote


class QuotesRepository:
    def create_quote_session(
        self,
        db: Session,
        *,
        from_country: str,
        from_city: str,
        to_country: str,
        to_city: str,
        shipment_type: str,
        weight_kg: Decimal,
        quantity: int,
        width_cm: Decimal,
        height_cm: Decimal,
        depth_cm: Decimal,
    ) -> QuoteSession:
        quote_session = QuoteSession(
            from_country=from_country,
            from_city=from_city,
            to_country=to_country,
            to_city=to_city,
            shipment_type=shipment_type,
            weight_kg=weight_kg,
            quantity=quantity,
            width_cm=width_cm,
            height_cm=height_cm,
            depth_cm=depth_cm,
        )
        db.add(quote_session)
        db.flush()
        return quote_session

    def create_rate_quote(
        self,
        db: Session,
        *,
        quote_session_id: int,
        carrier_code: str,
        carrier_name: str,
        tariff_name: str,
        price: Decimal,
        currency: str,
        eta_days_min: int,
        eta_days_max: int,
        badge: str | None = None,
        is_selected: bool = False,
    ) -> RateQuote:
        rate_quote = RateQuote(
            quote_session_id=quote_session_id,
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            tariff_name=tariff_name,
            price=price,
            currency=currency,
            eta_days_min=eta_days_min,
            eta_days_max=eta_days_max,
            badge=badge,
            is_selected=is_selected,
        )
        db.add(rate_quote)
        db.flush()
        return rate_quote

    def list_rate_quotes_by_session_id(
        self,
        db: Session,
        quote_session_id: int,
    ) -> Sequence[RateQuote]:
        stmt = (
            select(RateQuote)
            .where(RateQuote.quote_session_id == quote_session_id)
            .order_by(RateQuote.price.asc(), RateQuote.id.asc())
        )
        return db.scalars(stmt).all()