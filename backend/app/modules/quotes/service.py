from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.modules.quotes.repository import QuotesRepository
from app.modules.quotes.schemas import (
    RateQuoteItem,
    ShippingQuoteRequest,
    ShippingQuoteResponse,
)

"""
Сейчас расчёт тарифов реализован как временный mock-модуль в QuotesService для MVP.
Логика расчёта следующая: сначала определяется chargeable weight как максимум между
фактическим весом и объёмным весом, затем применяется коэффициент маршрута в зависимости
от направления доставки, после чего формируется базовая стоимость отправления. На основе
этой базовой стоимости генерируются 3 тестовых тарифа - Express, Standard и Economy -
с фиксированными сроками доставки и бейджами fastest, recommended и best_value.

Текущая реализация нужна для того, чтобы уже работал полный flow короткой формы
создание quote_session, сохранение rate_quotes и возврат вариантов тарифов на frontend.
В дальнейшем эту логику можно заменить на реальные тарифные таблицы, правила расчёта
и интеграции с курьерскими службами.
"""

class QuotesService:
    def __init__(self, repository: QuotesRepository | None = None) -> None:
        self.repository = repository or QuotesRepository()

    def calculate_quotes(
        self,
        db: Session,
        payload: ShippingQuoteRequest,
    ) -> ShippingQuoteResponse:
        quote_session = self.repository.create_quote_session(
            db,
            from_country=payload.from_country,
            from_city=payload.from_city,
            to_country=payload.to_country,
            to_city=payload.to_city,
            shipment_type=payload.shipment_type,
            weight_kg=payload.weight_kg,
            quantity=payload.quantity,
            width_cm=payload.width_cm,
            height_cm=payload.height_cm,
            depth_cm=payload.depth_cm,
        )

        mock_quotes = self._build_mock_quotes(payload)

        for quote in mock_quotes:
            self.repository.create_rate_quote(
                db,
                quote_session_id=quote_session.id,
                carrier_code=quote["carrier_code"],
                carrier_name=quote["carrier_name"],
                tariff_name=quote["tariff_name"],
                price=quote["price"],
                currency=quote["currency"],
                eta_days_min=quote["eta_days_min"],
                eta_days_max=quote["eta_days_max"],
                badge=quote["badge"],
                is_selected=False,
            )

        db.commit()

        saved_quotes = self.repository.list_rate_quotes_by_session_id(db, quote_session.id)

        return ShippingQuoteResponse(
            quote_session_id=quote_session.id,
            quotes=[
                RateQuoteItem(
                    id=item.id,
                    carrier_code=item.carrier_code,
                    carrier_name=item.carrier_name,
                    tariff_name=item.tariff_name,
                    price=item.price,
                    currency=item.currency,
                    eta_days_min=item.eta_days_min,
                    eta_days_max=item.eta_days_max,
                    badge=item.badge,
                    is_selected=item.is_selected,
                )
                for item in saved_quotes
            ],
        )

    def _build_mock_quotes(self, payload: ShippingQuoteRequest) -> list[dict]:
        route_multiplier = self._route_multiplier(
            payload.from_country,
            payload.to_country,
            payload.from_city,
            payload.to_city,
        )

        chargeable_weight = self._chargeable_weight(
            payload.weight_kg,
            payload.quantity,
            payload.width_cm,
            payload.height_cm,
            payload.depth_cm,
        )

        base_price = Decimal("1200.00") * route_multiplier + chargeable_weight * Decimal("900.00")

        shipment_type = payload.shipment_type.lower()
        if shipment_type == "document":
            base_price = max(base_price * Decimal("0.75"), Decimal("1500.00"))

        express_price = self._money(base_price * Decimal("1.45"))
        standard_price = self._money(base_price * Decimal("1.15"))
        economy_price = self._money(base_price * Decimal("0.95"))

        return [
            {
                "carrier_code": "azimuth",
                "carrier_name": "Azimuth",
                "tariff_name": "Express",
                "price": express_price,
                "currency": "KZT",
                "eta_days_min": 1,
                "eta_days_max": 2,
                "badge": "fastest",
            },
            {
                "carrier_code": "azimuth",
                "carrier_name": "Azimuth",
                "tariff_name": "Standard",
                "price": standard_price,
                "currency": "KZT",
                "eta_days_min": 2,
                "eta_days_max": 4,
                "badge": "recommended",
            },
            {
                "carrier_code": "partner_economy",
                "carrier_name": "Partner Economy",
                "tariff_name": "Economy",
                "price": economy_price,
                "currency": "KZT",
                "eta_days_min": 4,
                "eta_days_max": 7,
                "badge": "best_value",
            },
        ]

    def _chargeable_weight(
        self,
        weight_kg: Decimal,
        quantity: int,
        width_cm: Decimal,
        height_cm: Decimal,
        depth_cm: Decimal,
    ) -> Decimal:
        actual_weight = weight_kg * Decimal(quantity)
        volumetric_weight = ((width_cm * height_cm * depth_cm) / Decimal("5000")) * Decimal(quantity)
        return max(actual_weight, volumetric_weight)

    def _route_multiplier(
        self,
        from_country: str,
        to_country: str,
        from_city: str,
        to_city: str,
    ) -> Decimal:
        if from_country != to_country:
            return Decimal("2.40")
        if from_city.strip().lower() == to_city.strip().lower():
            return Decimal("0.85")
        return Decimal("1.35")

    def _money(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)