from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.carriers.tariff_engine import calculate_quotes as _engine_quotes
from app.modules.quotes.models import QuoteSession, RateQuote
from app.modules.quotes.schemas import (
    QuoteSelectionRequest,
    RateQuoteItem,
    ShippingQuoteRequest,
    ShippingQuoteResponse,
)


class QuotesService:

    def calculate_quotes(
        self,
        db: Session,
        payload: ShippingQuoteRequest,
    ) -> ShippingQuoteResponse:
        quotes = _engine_quotes(
            from_city=payload.from_city,
            to_city=payload.to_city,
            weight_kg=float(payload.weight_kg),
            quantity=int(payload.quantity),
            width_cm=float(payload.width_cm),
            height_cm=float(payload.height_cm),
            depth_cm=float(payload.depth_cm),
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
        )
        db.add(quote_session)
        db.flush()

        cheapest = min(quotes, key=lambda q: q.price, default=None)
        fastest  = min(quotes, key=lambda q: q.eta_days_min, default=None)

        rate_rows: list[RateQuote] = []
        for q in quotes:
            badge = None
            if cheapest and q.tariff_code == cheapest.tariff_code:
                badge = "Выгоднее всего"
            elif fastest and q.tariff_code == fastest.tariff_code:
                badge = "Быстрее всего"

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
            )
            rate_rows.append(rq)

        db.add_all(rate_rows)
        db.commit()
        db.refresh(quote_session)

        return ShippingQuoteResponse(
            quote_session_id=quote_session.id,
            quotes=[self._to_item(rq) for rq in rate_rows],
        )

    def get_quote_session(
        self,
        db: Session,
        session_id: int,
    ) -> ShippingQuoteResponse:
        session = db.query(QuoteSession).filter(QuoteSession.id == session_id).first()
        if not session:
            raise ValueError("Quote session not found.")
        rates = (
            db.query(RateQuote)
            .filter(RateQuote.quote_session_id == session_id)
            .all()
        )
        return ShippingQuoteResponse(
            quote_session_id=session.id,
            quotes=[self._to_item(r) for r in rates],
        )

    def select_quote(
        self,
        db: Session,
        quote_session_id: int,
        payload: QuoteSelectionRequest,
    ) -> ShippingQuoteResponse:
        # Снимаем предыдущий выбор в этой сессии
        db.query(RateQuote).filter(
            RateQuote.quote_session_id == quote_session_id,
            RateQuote.is_selected == True,
        ).update({"is_selected": False})

        # Ставим выбранный
        rate = (
            db.query(RateQuote)
            .filter(
                RateQuote.quote_session_id == quote_session_id,
                RateQuote.id == payload.rate_quote_id,
            )
            .first()
        )
        if not rate:
            raise ValueError("Rate quote not found.")

        rate.is_selected = True
        db.commit()

        return self.get_quote_session(db, quote_session_id)

    @staticmethod
    def _to_item(rq: RateQuote) -> RateQuoteItem:
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
        )