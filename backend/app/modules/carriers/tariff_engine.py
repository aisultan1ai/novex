"""
tariff_engine.py — движок расчёта тарифов.

Зоны:
  0 — внутригородская
  1 — между областными центрами РК
  2 — областной центр ↔ районный центр
  3 — удалённые населённые пункты

Объёмный вес = (Д × Ш × В) / 6000
Расчётный вес = max(фактический, объёмный), округл. до 0,5 кг вверх

При вызове с аргументом db= сначала пробуем тарифы из БД (carrier_tariff_rates).
Если таблица пуста — падаем обратно на хардкод Azimuth.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.modules.carriers.zone_mapper import get_zone

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Индексы колонок в таблице цен
_STD_Z0 = 0
_STD_Z1 = 1
_STD_Z2 = 2
_STD_Z3 = 3
_EXP_Z1 = 4
_EXP_Z2 = 5
_EXP_Z3 = 6

# ---------------------------------------------------------------------------
# Таблица «Стандарт» и «Экспресс»
# Формат: вес_кг: (std_z0, std_z1, std_z2, std_z3, exp_z1, exp_z2, exp_z3)
# ---------------------------------------------------------------------------
BESTSENDER_STANDARD_RATES: dict[float, tuple[int, ...]] = {
    0.3:  (1000,  2000,  2625,  3750,  2000,  3250,  5000),
    0.5:  (1000,  2000,  2625,  3750,  2810,  4060,  6035),
    1.0:  (1000,  2000,  2625,  3750,  3435,  4875,  7310),
    1.5:  (1000,  2000,  2625,  3750,  4125,  5375,  8335),
    2.0:  (1000,  2000,  2625,  3750,  4680,  5875,  9775),
    2.5:  (1310,  2060,  2935,  3810,  4930,  6060,  11075),
    3.0:  (1375,  2110,  3000,  3875,  5125,  6375,  11600),
    3.5:  (1435,  2150,  3060,  4060,  5310,  6875,  11935),
    4.0:  (1500,  2235,  3125,  4435,  5500,  7375,  12360),
    4.5:  (1560,  2310,  3310,  4810,  5680,  7875,  12810),
    5.0:  (1625,  2375,  3500,  5375,  5875,  8375,  13225),
    5.5:  (1685,  2435,  3685,  5435,  6250,  8875,  13685),
    6.0:  (1750,  2500,  3875,  5850,  7500,  9375,  14085),
    6.5:  (1810,  2560,  4125,  6000,  8000,  9875,  14560),
    7.0:  (1875,  2685,  4250,  6225,  8500,  10375, 14950),
    7.5:  (1935,  2810,  4435,  6375,  9000,  10875, 15435),
    8.0:  (2000,  2875,  4625,  6875,  9500,  11375, 15815),
    8.5:  (2060,  2935,  4945,  7375,  10000, 11875, 16250),
    9.0:  (2125,  3000,  5150,  8500,  10500, 12375, 16685),
    9.5:  (2250,  3060,  5355,  9060,  11000, 12875, 17185),
    10.0: (2435,  3125,  5625,  9625,  11500, 13375, 17560),
}

# Надбавка за каждые 0,5 кг свыше 10 кг
# (строка +0,5 кг из тарифного документа; exp_z3 — экстраполяция)
BESTSENDER_STANDARD_EXTRA_PER_HALF_KG: tuple[int, ...] = (
    125,   # Стандарт Зона 0
    160,   # Стандарт Зона 1
    280,   # Стандарт Зона 2
    560,   # Стандарт Зона 3
    750,   # Экспресс  Зона 1
    1500,  # Экспресс  Зона 2
    3000,  # Экспресс  Зона 3 (экстраполяция)
)

_SORTED_WEIGHTS: list[float] = sorted(BESTSENDER_STANDARD_RATES.keys())

# ---------------------------------------------------------------------------
# Таблица «Эконом» (наземный транспорт)
# Минимальная тарифицируемая масса — 10 кг
# ---------------------------------------------------------------------------
BESTSENDER_ECONOMY_BASE: tuple[int, int, int] = (5500, 7000, 9000)
BESTSENDER_ECONOMY_EXTRA_PER_KG: tuple[int, int, int] = (350, 480, 650)

BESTSENDER_ECONOMY_ETA: dict[int, tuple[int, int]] = {
    1: (3, 10),
    2: (5, 10),
    3: (7, 10),
}

BESTSENDER_STANDARD_ETA: dict[int, tuple[int, int]] = {
    0: (1, 1),
    1: (3, 7),
    2: (4, 10),
    3: (7, 14),
}

BESTSENDER_EXPRESS_ETA: dict[int, tuple[int, int]] = {
    0: (1, 1),
    1: (1, 3),
    2: (2, 4),
    3: (3, 5),
}

VOLUMETRIC_DIVISOR = 6000


def round_up_to_half(weight: float) -> float:
    """Округление до следующих 0,5 кг"""
    return math.ceil(weight * 2) / 2


def chargeable_weight(
    weight_kg: float,
    quantity: int,
    width_cm: float,
    height_cm: float,
    depth_cm: float,
) -> float:
    actual = weight_kg * quantity
    volumetric = (width_cm * height_cm * depth_cm / VOLUMETRIC_DIVISOR) * quantity
    return round_up_to_half(max(actual, volumetric))


def _lookup_standard_price(weight: float, col_idx: int) -> int:
    if weight <= 10.0:
        for threshold in _SORTED_WEIGHTS:
            if weight <= threshold:
                return BESTSENDER_STANDARD_RATES[threshold][col_idx]
        return BESTSENDER_STANDARD_RATES[10.0][col_idx]
    base = BESTSENDER_STANDARD_RATES[10.0][col_idx]
    extra_half_units = math.ceil((weight - 10.0) / 0.5)
    return base + extra_half_units * BESTSENDER_STANDARD_EXTRA_PER_HALF_KG[col_idx]


def _economy_price(weight: float, zone: int) -> int:
    billable = max(weight, 10.0)
    zone_idx = max(0, zone - 1)
    if billable <= 10.0:
        return BESTSENDER_ECONOMY_BASE[zone_idx]
    base = BESTSENDER_ECONOMY_BASE[zone_idx]
    extra_kg = math.ceil(billable - 10.0)
    return base + extra_kg * BESTSENDER_ECONOMY_EXTRA_PER_KG[zone_idx]


@dataclass
class QuoteResult:
    carrier_code: str
    carrier_name: str
    tariff_code: str
    tariff_name: str
    price: Decimal
    currency: str
    eta_days_min: int
    eta_days_max: int
    zone: int
    chargeable_kg: float


def calculate_quotes(
    from_city: str,
    to_city: str,
    weight_kg: float,
    quantity: int,
    width_cm: float,
    height_cm: float,
    depth_cm: float,
    db: "Session | None" = None,
) -> list[QuoteResult]:
    """
    Рассчитать стоимость по всем тарифам.
    Возвращает список, отсортированный по цене (от дешёвого к дорогому).

    Если передан db= — пробует загрузить тарифы из БД (carrier_tariff_rates).
    Если в БД нет активных ставок — использует встроенную таблицу Azimuth.
    """
    fallback_zone = get_zone(from_city, to_city)
    kg = chargeable_weight(weight_kg, quantity, width_cm, height_cm, depth_cm)

    if db is not None:
        db_results = _calculate_from_db(db, from_city, to_city, fallback_zone, kg)
        if db_results:
            logger.debug(
                "tariff_engine: DB rates used (%d quotes, kg=%.2f)",
                len(db_results),
                kg,
            )
            db_results.sort(key=lambda r: (r.price, r.eta_days_min))
            return db_results
        logger.debug("tariff_engine: DB has no rates, falling back to hardcoded Azimuth table")

    return _calculate_hardcoded(fallback_zone, kg)


def _calculate_hardcoded(zone: int, kg: float) -> list[QuoteResult]:
    """Расчёт по встроенной таблице Azimuth (fallback)."""
    results: list[QuoteResult] = []

    # 1. Стандарт (зоны 0-3)
    col_map_std = {0: _STD_Z0, 1: _STD_Z1, 2: _STD_Z2, 3: _STD_Z3}
    std_price = _lookup_standard_price(kg, col_map_std.get(zone, _STD_Z3))
    std_eta = BESTSENDER_STANDARD_ETA[zone]
    results.append(QuoteResult(
        carrier_code="azimuth", carrier_name="Azimuth",
        tariff_code="standard", tariff_name="Стандарт",
        price=Decimal(str(std_price)), currency="KZT",
        eta_days_min=std_eta[0], eta_days_max=std_eta[1],
        zone=zone, chargeable_kg=kg,
    ))

    # 2. Экспресс (зоны 0-3; для zone 0 = тариф std_z0)
    if zone == 0:
        exp_price = _lookup_standard_price(kg, _STD_Z0)
    else:
        col_map_exp = {1: _EXP_Z1, 2: _EXP_Z2, 3: _EXP_Z3}
        exp_price = _lookup_standard_price(kg, col_map_exp.get(zone, _EXP_Z3))
    exp_eta = BESTSENDER_EXPRESS_ETA[zone]
    results.append(QuoteResult(
        carrier_code="azimuth", carrier_name="Azimuth",
        tariff_code="express", tariff_name="Экспресс",
        price=Decimal(str(exp_price)), currency="KZT",
        eta_days_min=exp_eta[0], eta_days_max=exp_eta[1],
        zone=zone, chargeable_kg=kg,
    ))

    # 3. Эконом — только для межгородских маршрутов (zone >= 1)
    if zone >= 1:
        eco_price = _economy_price(kg, zone)
        eco_eta = BESTSENDER_ECONOMY_ETA.get(zone, (7, 14))
        results.append(QuoteResult(
            carrier_code="azimuth", carrier_name="Azimuth",
            tariff_code="economy", tariff_name="Эконом",
            price=Decimal(str(eco_price)), currency="KZT",
            eta_days_min=eco_eta[0], eta_days_max=eco_eta[1],
            zone=zone, chargeable_kg=kg,
        ))

    results.sort(key=lambda r: (r.price, r.eta_days_min))
    return results


def _db_rate_price(rate: object, kg: float) -> int:
    """
    Рассчитать цену по одной строке CarrierTariffRate.

    Формула:
      base_price  — если kg ≤ weight_to_kg (или weight_to_kg IS NULL без надбавки)
      base_price + ceil((kg - weight_from_kg) / per_unit_weight_kg) * per_unit_price
                  — для открытого верхнего диапазона с per_unit_price
    """
    base = float(rate.base_price)  # type: ignore[attr-defined]
    wf = float(rate.weight_from_kg)  # type: ignore[attr-defined]
    per_price = float(rate.per_unit_price) if rate.per_unit_price is not None else 0.0  # type: ignore[attr-defined]
    per_w = float(rate.per_unit_weight_kg) if rate.per_unit_weight_kg is not None else 0.5  # type: ignore[attr-defined]

    if per_price > 0 and kg > wf:
        excess = kg - wf
        extra_units = math.ceil(excess / per_w)
        return int(base + extra_units * per_price)
    return int(base)


def _zone_from_carrier_cities(
    from_city: str,
    to_city: str,
    zone_cities: list,
) -> int | None:
    """
    Определить зону маршрута по таблице CarrierZoneCity.
    Возвращает None если хотя бы один из городов не найден.
    """
    frm = from_city.strip().lower()
    too = to_city.strip().lower()

    if frm == too:
        return 0

    city_map: dict[str, int] = {zc.city_name_normalized: zc.zone for zc in zone_cities}

    from_zone = city_map.get(frm)
    to_zone = city_map.get(too)

    if to_zone is not None:
        # Зона маршрута — зона города назначения.
        # Если оба города найдены и от_зона > до_зоны — берём максимум
        # (дорогостоящий конец определяет тариф).
        if from_zone is not None:
            return max(from_zone, to_zone)
        return to_zone

    return None


def _calculate_from_db(
    db: "Session",
    from_city: str,
    to_city: str,
    fallback_zone: int,
    kg: float,
) -> list[QuoteResult]:
    """Загружает тарифы из БД и строит котировки для всех активных перевозчиков."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.modules.carriers.models import Carrier, CarrierService, CarrierTariffRate

    carriers = db.scalars(
        select(Carrier)
        .where(Carrier.is_active.is_(True))
        .options(
            selectinload(Carrier.services).selectinload(CarrierService.tariff_rates),
            selectinload(Carrier.zone_cities),
        )
    ).all()

    results: list[QuoteResult] = []

    for carrier in carriers:
        # Пробуем определить зону по городам конкретного перевозчика;
        # если не найдено — используем хардкодный fallback.
        zone = _zone_from_carrier_cities(from_city, to_city, carrier.zone_cities)
        if zone is None:
            zone = fallback_zone
            logger.debug(
                "tariff_engine: carrier=%s cities not in zone_cities, using fallback zone=%d",
                carrier.code, zone,
            )
        else:
            logger.debug(
                "tariff_engine: carrier=%s zone=%d from DB city mapping (%s→%s)",
                carrier.code, zone, from_city, to_city,
            )

        for service in carrier.services:
            if not service.is_active:
                continue

            zone_rates: list[CarrierTariffRate] = sorted(
                [r for r in service.tariff_rates if r.is_active and r.zone == zone],
                key=lambda r: float(r.weight_from_kg),
            )

            if not zone_rates:
                continue

            applicable = None
            for rate in zone_rates:
                wf = float(rate.weight_from_kg)
                wt = float(rate.weight_to_kg) if rate.weight_to_kg is not None else None
                if wf <= kg and (wt is None or kg <= wt):
                    applicable = rate
                    break

            if applicable is None:
                applicable = zone_rates[-1]

            price = _db_rate_price(applicable, kg)
            eta_min = applicable.eta_days_min if applicable.eta_days_min is not None else 1
            eta_max = applicable.eta_days_max if applicable.eta_days_max is not None else 14

            results.append(QuoteResult(
                carrier_code=carrier.code,
                carrier_name=carrier.name,
                tariff_code=service.code,
                tariff_name=service.name,
                price=Decimal(str(price)),
                currency=applicable.currency,
                eta_days_min=eta_min,
                eta_days_max=eta_max,
                zone=zone,
                chargeable_kg=kg,
            ))

    return results