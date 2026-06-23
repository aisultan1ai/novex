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

import asyncio
import logging
import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx

from app.modules.carriers.zone_mapper import get_zone
from app.modules.carriers.cse_geography import city_to_postcode_geo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Exline service-code → (tariff_code, tariff_name, eta_min, eta_max)
_EXLINE_SERVICES: dict[str, tuple[str, str, int, int]] = {
    "1": ("standard", "Стандарт",  3, 10),
    "2": ("express",  "Экспресс",  1,  3),
}
_EXLINE_TIMEOUT = 8  # секунд; не блокируем пользователя дольше


def _xml_esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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
    0.3: (1000, 2000, 2625, 3750, 2000, 3250, 5000),
    0.5: (1000, 2000, 2625, 3750, 2810, 4060, 6035),
    1.0: (1000, 2000, 2625, 3750, 3435, 4875, 7310),
    1.5: (1000, 2000, 2625, 3750, 4125, 5375, 8335),
    2.0: (1000, 2000, 2625, 3750, 4680, 5875, 9775),
    2.5: (1310, 2060, 2935, 3810, 4930, 6060, 11075),
    3.0: (1375, 2110, 3000, 3875, 5125, 6375, 11600),
    3.5: (1435, 2150, 3060, 4060, 5310, 6875, 11935),
    4.0: (1500, 2235, 3125, 4435, 5500, 7375, 12360),
    4.5: (1560, 2310, 3310, 4810, 5680, 7875, 12810),
    5.0: (1625, 2375, 3500, 5375, 5875, 8375, 13225),
    5.5: (1685, 2435, 3685, 5435, 6250, 8875, 13685),
    6.0: (1750, 2500, 3875, 5850, 7500, 9375, 14085),
    6.5: (1810, 2560, 4125, 6000, 8000, 9875, 14560),
    7.0: (1875, 2685, 4250, 6225, 8500, 10375, 14950),
    7.5: (1935, 2810, 4435, 6375, 9000, 10875, 15435),
    8.0: (2000, 2875, 4625, 6875, 9500, 11375, 15815),
    8.5: (2060, 2935, 4945, 7375, 10000, 11875, 16250),
    9.0: (2125, 3000, 5150, 8500, 10500, 12375, 16685),
    9.5: (2250, 3060, 5355, 9060, 11000, 12875, 17185),
    10.0: (2435, 3125, 5625, 9625, 11500, 13375, 17560),
}

# Надбавка за каждые 0,5 кг свыше 10 кг
# (строка +0,5 кг из тарифного документа; exp_z3 — экстраполяция)
BESTSENDER_STANDARD_EXTRA_PER_HALF_KG: tuple[int, ...] = (
    125,  # Стандарт Зона 0
    160,  # Стандарт Зона 1
    280,  # Стандарт Зона 2
    560,  # Стандарт Зона 3
    750,  # Экспресс  Зона 1
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
    db: Session | None = None,
    include_live: bool = True,
) -> list[QuoteResult]:
    """
    Рассчитать стоимость по всем тарифам.
    Возвращает список, отсортированный по цене (от дешёвого к дорогому).

    Если передан db= — пробует загрузить тарифы из БД (carrier_tariff_rates).
    Если в БД нет активных ставок — использует встроенную таблицу Azimuth.

    include_live=False — пропустить вызов Exline API (используется когда вызывающий
    код хочет освободить DB-соединение перед внешним HTTP-запросом).
    """
    fallback_zone = get_zone(from_city, to_city)
    kg = chargeable_weight(weight_kg, quantity, width_cm, height_cm, depth_cm)

    results: list[QuoteResult] = []

    if db is not None:
        db_results = _calculate_from_db(db, from_city, to_city, fallback_zone, kg)
        if db_results:
            logger.debug(
                "tariff_engine: DB rates used (%d quotes, kg=%.2f)",
                len(db_results),
                kg,
            )
            results = db_results
        else:
            logger.debug(
                "tariff_engine: DB has no rates, falling back to hardcoded Azimuth table"
            )
            results = _calculate_hardcoded(fallback_zone, kg)
    else:
        results = _calculate_hardcoded(fallback_zone, kg)

    if include_live:
        # Добавляем live-котировки Exline только если DB не вернула Exline-ставки
        if not any(r.carrier_code == "exline" for r in results):
            results.extend(_calculate_exline_live(from_city, to_city, kg))
        results.sort(key=lambda r: (r.price, r.eta_days_min))

    return results


def fetch_exline_quotes(
    from_city: str,
    to_city: str,
    weight_kg: float,
    quantity: int,
    width_cm: float,
    height_cm: float,
    depth_cm: float,
) -> list[QuoteResult]:
    """Только внешний вызов Exline — без DB. Вызывать после закрытия DB-соединения."""
    kg = chargeable_weight(weight_kg, quantity, width_cm, height_cm, depth_cm)
    return _calculate_exline_live(from_city, to_city, kg)


async def calculate_quotes_async(
    from_city: str,
    to_city: str,
    weight_kg: float,
    quantity: int,
    width_cm: float,
    height_cm: float,
    depth_cm: float,
    db: AsyncSession,
) -> list[QuoteResult]:
    """Async version для /api/shipping/quote — DB и Exline HTTP не держат соединение одновременно."""
    fallback_zone = get_zone(from_city, to_city)
    kg = chargeable_weight(weight_kg, quantity, width_cm, height_cm, depth_cm)

    db_results = await _calculate_from_db_async(db, from_city, to_city, fallback_zone, kg)
    results: list[QuoteResult] = db_results if db_results else _calculate_hardcoded(fallback_zone, kg)

    # Run Exline and CSE live calls concurrently
    live_tasks = []
    if not any(r.carrier_code == "exline" for r in results):
        live_tasks.append(_calculate_exline_live_async(from_city, to_city, kg))
    if not any(r.carrier_code == "cse" for r in results):
        live_tasks.append(_calculate_cse_live_async(from_city, to_city, kg))

    if live_tasks:
        live_lists = await asyncio.gather(*live_tasks, return_exceptions=True)
        for live in live_lists:
            if isinstance(live, list):
                results.extend(live)
            elif isinstance(live, Exception):
                logger.debug("Live carrier task failed: %s", live)

    results.sort(key=lambda r: (r.price, r.eta_days_min))
    return results


def _calculate_hardcoded(zone: int, kg: float) -> list[QuoteResult]:
    """Расчёт по встроенной таблице Azimuth (fallback)."""
    results: list[QuoteResult] = []

    # 1. Стандарт (зоны 0-3)
    col_map_std = {0: _STD_Z0, 1: _STD_Z1, 2: _STD_Z2, 3: _STD_Z3}
    std_price = _lookup_standard_price(kg, col_map_std.get(zone, _STD_Z3))
    std_eta = BESTSENDER_STANDARD_ETA[zone]
    results.append(
        QuoteResult(
            carrier_code="azimuth",
            carrier_name="Azimuth",
            tariff_code="standard",
            tariff_name="Стандарт",
            price=Decimal(str(std_price)),
            currency="KZT",
            eta_days_min=std_eta[0],
            eta_days_max=std_eta[1],
            zone=zone,
            chargeable_kg=kg,
        )
    )

    # 2. Экспресс (зоны 0-3; для zone 0 = тариф std_z0)
    if zone == 0:
        exp_price = _lookup_standard_price(kg, _STD_Z0)
    else:
        col_map_exp = {1: _EXP_Z1, 2: _EXP_Z2, 3: _EXP_Z3}
        exp_price = _lookup_standard_price(kg, col_map_exp.get(zone, _EXP_Z3))
    exp_eta = BESTSENDER_EXPRESS_ETA[zone]
    results.append(
        QuoteResult(
            carrier_code="azimuth",
            carrier_name="Azimuth",
            tariff_code="express",
            tariff_name="Экспресс",
            price=Decimal(str(exp_price)),
            currency="KZT",
            eta_days_min=exp_eta[0],
            eta_days_max=exp_eta[1],
            zone=zone,
            chargeable_kg=kg,
        )
    )

    # 3. Эконом — только для межгородских маршрутов (zone >= 1)
    if zone >= 1:
        eco_price = _economy_price(kg, zone)
        eco_eta = BESTSENDER_ECONOMY_ETA.get(zone, (7, 14))
        results.append(
            QuoteResult(
                carrier_code="azimuth",
                carrier_name="Azimuth",
                tariff_code="economy",
                tariff_name="Эконом",
                price=Decimal(str(eco_price)),
                currency="KZT",
                eta_days_min=eco_eta[0],
                eta_days_max=eco_eta[1],
                zone=zone,
                chargeable_kg=kg,
            )
        )

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
    per_w = (
        float(rate.per_unit_weight_kg) if rate.per_unit_weight_kg is not None else 0.5  # type: ignore[attr-defined]
    )

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


def _quotes_from_carriers(
    carriers: list,
    from_city: str,
    to_city: str,
    fallback_zone: int,
    kg: float,
) -> list[QuoteResult]:
    """Pure-Python processing — shared by sync and async DB paths."""
    results: list[QuoteResult] = []
    for carrier in carriers:
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

            zone_rates = sorted(
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


def _calculate_from_db(
    db: Session,
    from_city: str,
    to_city: str,
    fallback_zone: int,
    kg: float,
) -> list[QuoteResult]:
    """Загружает тарифы из БД и строит котировки для всех активных перевозчиков."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.modules.carriers.models import Carrier, CarrierService

    carriers = db.scalars(
        select(Carrier)
        .where(Carrier.is_active.is_(True))
        .options(
            selectinload(Carrier.services).selectinload(CarrierService.tariff_rates),
            selectinload(Carrier.zone_cities),
        )
    ).all()

    results = _quotes_from_carriers(carriers, from_city, to_city, fallback_zone, kg)
    if results:
        logger.debug("tariff_engine: DB rates used (%d quotes, kg=%.2f)", len(results), kg)
    else:
        logger.debug("tariff_engine: DB has no rates, falling back to hardcoded Azimuth table")
    return results


async def _calculate_from_db_async(
    db: AsyncSession,
    from_city: str,
    to_city: str,
    fallback_zone: int,
    kg: float,
) -> list[QuoteResult]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.modules.carriers.models import Carrier, CarrierService

    result = await db.execute(
        select(Carrier)
        .where(Carrier.is_active.is_(True))
        .options(
            selectinload(Carrier.services).selectinload(CarrierService.tariff_rates),
            selectinload(Carrier.zone_cities),
        )
    )
    carriers = result.scalars().all()

    results = _quotes_from_carriers(carriers, from_city, to_city, fallback_zone, kg)
    if results:
        logger.debug("tariff_engine: DB rates used (%d quotes, kg=%.2f)", len(results), kg)
    else:
        logger.debug("tariff_engine: DB has no rates, falling back to hardcoded Azimuth table")
    return results


# ---------------------------------------------------------------------------
# Exline live calculator
# ---------------------------------------------------------------------------

def _call_exline_calculator(
    from_city: str,
    to_city: str,
    kg: float,
    service_code: str,
    extra: str,
    login: str,
    password: str,
    api_url: str,
) -> QuoteResult | None:
    tariff_code, tariff_name, eta_min, eta_max = _EXLINE_SERVICES[service_code]
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<calculator>"
        f'<auth extra="{_xml_esc(extra)}" login="{_xml_esc(login)}" pass="{_xml_esc(password)}"/>'
        "<order>"
        "<pricetype>CUSTOMER</pricetype>"
        f"<sender><town>{_xml_esc(from_city)}</town></sender>"
        f"<receiver><town>{_xml_esc(to_city)}</town></receiver>"
        f"<weight>{kg:.3f}</weight>"
        f"<service>{_xml_esc(service_code)}</service>"
        "<paytype>NO</paytype>"
        "</order>"
        "</calculator>"
    )
    try:
        resp = httpx.post(
            api_url,
            content=xml.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=_EXLINE_TIMEOUT,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as exc:
        logger.warning(
            "Exline calculator failed (service=%s, %s→%s): %s",
            service_code, from_city, to_city, exc,
        )
        return None

    if root.attrib.get("error") == "1":
        logger.warning("Exline calculator: auth error (service=%s)", service_code)
        return None

    calc_el = root.find("calc")
    if calc_el is None:
        return None

    price_el = calc_el.find("price")
    if price_el is None or not (price_el.text or "").strip():
        return None

    try:
        price = Decimal((price_el.text or "").strip())
    except Exception:
        return None

    min_el = calc_el.find("mindeliverydays")
    max_el = calc_el.find("maxdeliverydays")
    zone_el = calc_el.find("zone")

    if min_el is not None and (min_el.text or "").strip().lstrip("-").isdigit():
        val = int(min_el.text.strip())
        if val > 0:
            eta_min = val  # type: ignore[assignment]
    if max_el is not None and (max_el.text or "").strip().lstrip("-").isdigit():
        val = int(max_el.text.strip())
        if val > 0:
            eta_max = val  # type: ignore[assignment]

    zone = 1
    if zone_el is not None and (zone_el.text or "").strip().lstrip("-").isdigit():
        zone = max(0, int(zone_el.text.strip()))

    return QuoteResult(
        carrier_code="exline",
        carrier_name="Exline",
        tariff_code=tariff_code,
        tariff_name=tariff_name,
        price=price,
        currency="KZT",
        eta_days_min=eta_min,
        eta_days_max=eta_max,
        zone=zone,
        chargeable_kg=kg,
    )


def _calculate_exline_live(
    from_city: str,
    to_city: str,
    kg: float,
) -> list[QuoteResult]:
    extra = os.getenv("EXLINE_EXTRA", "")
    login = os.getenv("EXLINE_LOGIN", "")
    password = os.getenv("EXLINE_PASSWORD", "")
    api_url = os.getenv("EXLINE_API_URL", "https://home.courierexe.ru/api/").rstrip("/") + "/"

    if not extra or not login:
        return []

    results: list[QuoteResult] = []
    for service_code in _EXLINE_SERVICES:
        quote = _call_exline_calculator(
            from_city, to_city, kg, service_code,
            extra, login, password, api_url,
        )
        if quote is not None:
            results.append(quote)

    logger.debug(
        "Exline: %d quotes for %s→%s kg=%.2f", len(results), from_city, to_city, kg
    )
    return results


async def _call_exline_calculator_async(
    from_city: str,
    to_city: str,
    kg: float,
    service_code: str,
    extra: str,
    login: str,
    password: str,
    api_url: str,
) -> QuoteResult | None:
    tariff_code, tariff_name, eta_min, eta_max = _EXLINE_SERVICES[service_code]
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<calculator>"
        f'<auth extra="{_xml_esc(extra)}" login="{_xml_esc(login)}" pass="{_xml_esc(password)}"/>'
        "<order>"
        "<pricetype>CUSTOMER</pricetype>"
        f"<sender><town>{_xml_esc(from_city)}</town></sender>"
        f"<receiver><town>{_xml_esc(to_city)}</town></receiver>"
        f"<weight>{kg:.3f}</weight>"
        f"<service>{_xml_esc(service_code)}</service>"
        "<paytype>NO</paytype>"
        "</order>"
        "</calculator>"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                api_url,
                content=xml.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=_EXLINE_TIMEOUT,
            )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as exc:
        logger.warning(
            "Exline calculator failed (service=%s, %s→%s): %s",
            service_code, from_city, to_city, exc,
        )
        return None

    if root.attrib.get("error") == "1":
        logger.warning("Exline calculator: auth error (service=%s)", service_code)
        return None

    calc_el = root.find("calc")
    if calc_el is None:
        return None

    price_el = calc_el.find("price")
    if price_el is None or not (price_el.text or "").strip():
        return None

    try:
        price = Decimal((price_el.text or "").strip())
    except Exception:
        return None

    min_el = calc_el.find("mindeliverydays")
    max_el = calc_el.find("maxdeliverydays")
    zone_el = calc_el.find("zone")

    if min_el is not None and (min_el.text or "").strip().lstrip("-").isdigit():
        val = int(min_el.text.strip())
        if val > 0:
            eta_min = val  # type: ignore[assignment]
    if max_el is not None and (max_el.text or "").strip().lstrip("-").isdigit():
        val = int(max_el.text.strip())
        if val > 0:
            eta_max = val  # type: ignore[assignment]

    zone = 1
    if zone_el is not None and (zone_el.text or "").strip().lstrip("-").isdigit():
        zone = max(0, int(zone_el.text.strip()))

    return QuoteResult(
        carrier_code="exline",
        carrier_name="Exline",
        tariff_code=tariff_code,
        tariff_name=tariff_name,
        price=price,
        currency="KZT",
        eta_days_min=eta_min,
        eta_days_max=eta_max,
        zone=zone,
        chargeable_kg=kg,
    )


async def _calculate_exline_live_async(
    from_city: str,
    to_city: str,
    kg: float,
) -> list[QuoteResult]:
    extra = os.getenv("EXLINE_EXTRA", "")
    login = os.getenv("EXLINE_LOGIN", "")
    password = os.getenv("EXLINE_PASSWORD", "")
    api_url = os.getenv("EXLINE_API_URL", "https://home.courierexe.ru/api/").rstrip("/") + "/"

    if not extra or not login:
        return []

    # All Exline service calls run concurrently — no sequential blocking
    quotes = await asyncio.gather(*[
        _call_exline_calculator_async(from_city, to_city, kg, service_code, extra, login, password, api_url)
        for service_code in _EXLINE_SERVICES
    ])
    results = [q for q in quotes if q is not None]

    logger.debug(
        "Exline async: %d quotes for %s→%s kg=%.2f", len(results), from_city, to_city, kg
    )
    return results


# ---------------------------------------------------------------------------
# CSE live calculator (async)
# ---------------------------------------------------------------------------

_CSE_TIMEOUT = 10  # seconds


async def _call_cse_calc_async(
    from_geo: str,
    to_geo: str,
    kg: float,
    login: str,
    password: str,
    api_url: str,
) -> list[QuoteResult]:
    from app.modules.carriers.api_clients.cse import (
        build_envelope,
        extract_return,
        parse_calc_response,
        _build_calc_inner,
    )

    inner = _build_calc_inner(login, password, from_geo, to_geo, kg, 1, "")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                api_url,
                content=build_envelope("Calc", inner),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": f'"http://web.cse.ru/WS/Web1CWS/Calc"',
                },
                timeout=_CSE_TIMEOUT,
            )
        resp.raise_for_status()
        ret = extract_return(resp.text, "Calc")
        tariffs = parse_calc_response(ret)
    except Exception as exc:
        logger.warning("CSE calc failed (%s→%s): %s", from_geo, to_geo, exc)
        return []

    zone = get_zone(from_geo, to_geo)
    results: list[QuoteResult] = []
    for t in tariffs:
        results.append(QuoteResult(
            carrier_code="cse",
            carrier_name="CSE",
            tariff_code=t.get("tariff_guid", "cse_tariff"),
            tariff_name=t["service_name"],
            price=Decimal(str(round(t["price"], 2))),
            currency=t.get("currency", "RUB"),
            eta_days_min=t["min_days"],
            eta_days_max=t["max_days"],
            zone=zone,
            chargeable_kg=kg,
        ))

    logger.debug("CSE async: %d quotes for %s→%s kg=%.2f", len(results), from_geo, to_geo, kg)
    return results


async def _calculate_cse_live_async(
    from_city: str,
    to_city: str,
    kg: float,
) -> list[QuoteResult]:
    login = os.getenv("CSE_LOGIN", "")
    password = os.getenv("CSE_PASSWORD", "")
    api_url = os.getenv("CSE_API_URL", "http://web.cse.ru/1c/ws/Web1C.1cws")

    if not login:
        return []

    from_geo = city_to_postcode_geo(from_city)
    to_geo = city_to_postcode_geo(to_city)

    if not from_geo or not to_geo:
        logger.debug(
            "CSE: skipping %s→%s — no postcode mapping available", from_city, to_city
        )
        return []

    return await _call_cse_calc_async(from_geo, to_geo, kg, login, password, api_url)
