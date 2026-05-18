"""
seed.py — заполняет БД начальными данными.

Что делает:
  1. Создаёт перевозчика «Azimuth» (code=azimuth)
  2. Создаёт три услуги: standard, express, economy
  3. Заполняет тарифные ставки из таблицы tariff_engine.py
  4. Заполняет zone_cities из zone_mapper.py

Идемпотентен: повторный запуск ничего не сломает.

Использование:
  python -m scripts.seed                    # через DATABASE_URL из окружения
  DATABASE_URL=postgresql://... python -m scripts.seed
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed")


def main() -> None:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.modules.carriers.models import (
        Carrier,
        CarrierService,
        CarrierTariffRate,
        CarrierZoneCity,
    )
    from app.modules.carriers.tariff_engine import (
        _EXP_Z1,
        _EXP_Z2,
        _EXP_Z3,
        _SORTED_WEIGHTS,
        _STD_Z0,
        _STD_Z1,
        _STD_Z2,
        _STD_Z3,
        BESTSENDER_ECONOMY_BASE,
        BESTSENDER_ECONOMY_ETA,
        BESTSENDER_ECONOMY_EXTRA_PER_KG,
        BESTSENDER_EXPRESS_ETA,
        BESTSENDER_STANDARD_ETA,
        BESTSENDER_STANDARD_EXTRA_PER_HALF_KG,
        BESTSENDER_STANDARD_RATES,
    )
    from app.modules.carriers.zone_mapper import DISTRICT_CENTERS, REGIONAL_CENTERS

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with Session(engine) as db:
        # ── 1. Carrier ────────────────────────────────────────────────────────
        carrier = db.scalar(select(Carrier).where(Carrier.code == "azimuth"))
        if carrier is None:
            carrier = Carrier(
                code="azimuth",
                name="Azimuth",
                description=(
                    "Казахстанская курьерская служба — стандарт, экспресс, эконом"
                ),
                is_active=True,
            )
            db.add(carrier)
            db.flush()
            log.info("Carrier created: azimuth (id=%d)", carrier.id)
        else:
            log.info("Carrier already exists: azimuth (id=%d)", carrier.id)

        # ── 2. Services ───────────────────────────────────────────────────────
        def get_or_create_service(
            code: str, name: str, shipment_type: str
        ) -> CarrierService:
            svc = db.scalar(
                select(CarrierService).where(
                    CarrierService.carrier_id == carrier.id,
                    CarrierService.code == code,
                )
            )
            if svc is None:
                svc = CarrierService(
                    carrier_id=carrier.id,
                    code=code,
                    name=name,
                    shipment_type=shipment_type,
                    is_active=True,
                )
                db.add(svc)
                db.flush()
                log.info("  Service created: %s (id=%d)", code, svc.id)
            else:
                log.info("  Service already exists: %s (id=%d)", code, svc.id)
            return svc

        svc_standard = get_or_create_service("standard", "Стандарт", "standard")
        svc_express = get_or_create_service("express", "Экспресс", "express")
        svc_economy = get_or_create_service("economy", "Эконом (авто)", "economy")

        # ── 3. Tariff rates ───────────────────────────────────────────────────
        # Checks if any rate already exists — skip seeding if so
        existing_rate_count = db.scalar(
            select(CarrierTariffRate)
            .where(
                CarrierTariffRate.service_id.in_(
                    [
                        svc_standard.id,
                        svc_express.id,
                        svc_economy.id,
                    ]
                )
            )
            .limit(1)
        )
        if existing_rate_count is not None:
            log.info("Tariff rates already seeded — skipping rates")
        else:
            rates_added = 0

            # Helper to build weight brackets from the lookup table
            # BESTSENDER_STANDARD_RATES is a dict {upper_kg: (col0, col1, ...)}
            # Brackets: (prev_upper, current_upper]
            def _standard_rate_rows() -> list[tuple[float, float | None, int]]:
                """Returns (weight_from, weight_to, col_index) for each zone col."""
                rows = []
                prev = 0.0
                for w in _SORTED_WEIGHTS:
                    rows.append((prev, w))
                    prev = w
                # Open-ended bracket for > 10 kg
                rows.append((10.0, None))
                return rows

            brackets = _standard_rate_rows()

            # Standard: zones 0, 1, 2, 3
            std_zone_cols = {0: _STD_Z0, 1: _STD_Z1, 2: _STD_Z2, 3: _STD_Z3}
            for zone, col_idx in std_zone_cols.items():
                eta = BESTSENDER_STANDARD_ETA[zone]
                for wf, wt in brackets:
                    if wt is not None:
                        base_price = BESTSENDER_STANDARD_RATES[wt][col_idx]
                        per_unit_price = None
                        per_unit_weight_kg = None
                    else:
                        # > 10 kg: open bracket with per-0.5-kg surcharge
                        base_price = BESTSENDER_STANDARD_RATES[10.0][col_idx]
                        per_unit_price = float(
                            BESTSENDER_STANDARD_EXTRA_PER_HALF_KG[col_idx]
                        )
                        per_unit_weight_kg = 0.5

                    db.add(
                        CarrierTariffRate(
                            service_id=svc_standard.id,
                            zone=zone,
                            weight_from_kg=wf,
                            weight_to_kg=wt,
                            base_price=base_price,
                            per_unit_price=per_unit_price,
                            per_unit_weight_kg=per_unit_weight_kg,
                            currency="KZT",
                            eta_days_min=eta[0],
                            eta_days_max=eta[1],
                            is_active=True,
                        )
                    )
                    rates_added += 1

            # Express: zone 0 (same as std_z0), zones 1, 2, 3 (exp cols)
            exp_zone_cols = {0: _STD_Z0, 1: _EXP_Z1, 2: _EXP_Z2, 3: _EXP_Z3}
            for zone, col_idx in exp_zone_cols.items():
                eta = BESTSENDER_EXPRESS_ETA[zone]
                for wf, wt in brackets:
                    if wt is not None:
                        base_price = BESTSENDER_STANDARD_RATES[wt][col_idx]
                        per_unit_price = None
                        per_unit_weight_kg = None
                    else:
                        base_price = BESTSENDER_STANDARD_RATES[10.0][col_idx]
                        per_unit_price = float(
                            BESTSENDER_STANDARD_EXTRA_PER_HALF_KG[col_idx]
                        )
                        per_unit_weight_kg = 0.5

                    db.add(
                        CarrierTariffRate(
                            service_id=svc_express.id,
                            zone=zone,
                            weight_from_kg=wf,
                            weight_to_kg=wt,
                            base_price=base_price,
                            per_unit_price=per_unit_price,
                            per_unit_weight_kg=per_unit_weight_kg,
                            currency="KZT",
                            eta_days_min=eta[0],
                            eta_days_max=eta[1],
                            is_active=True,
                        )
                    )
                    rates_added += 1

            # Economy: zones 1, 2, 3 only; min billable = 10 kg
            for zone in (1, 2, 3):
                zi = zone - 1  # index into ECONOMY arrays
                eta = BESTSENDER_ECONOMY_ETA[zone]
                base = BESTSENDER_ECONOMY_BASE[zi]
                extra = BESTSENDER_ECONOMY_EXTRA_PER_KG[zi]

                # Rate for < 10 kg (charged as 10 kg)
                db.add(
                    CarrierTariffRate(
                        service_id=svc_economy.id,
                        zone=zone,
                        weight_from_kg=0.0,
                        weight_to_kg=10.0,
                        base_price=base,
                        per_unit_price=None,
                        per_unit_weight_kg=None,
                        currency="KZT",
                        eta_days_min=eta[0],
                        eta_days_max=eta[1],
                        is_active=True,
                    )
                )
                rates_added += 1

                # Rate for > 10 kg (base + extra per each kg above 10)
                db.add(
                    CarrierTariffRate(
                        service_id=svc_economy.id,
                        zone=zone,
                        weight_from_kg=10.0,
                        weight_to_kg=None,
                        base_price=base,
                        per_unit_price=float(extra),
                        per_unit_weight_kg=1.0,
                        currency="KZT",
                        eta_days_min=eta[0],
                        eta_days_max=eta[1],
                        is_active=True,
                    )
                )
                rates_added += 1

            db.flush()
            log.info("Tariff rates added: %d", rates_added)

        # ── 4. Zone cities ────────────────────────────────────────────────────
        existing_city_count = db.scalar(
            select(CarrierZoneCity)
            .where(CarrierZoneCity.carrier_id == carrier.id)
            .limit(1)
        )
        if existing_city_count is not None:
            log.info("Zone cities already seeded — skipping cities")
        else:
            cities_added = 0
            seen: set[str] = set()

            def add_city(name: str, zone: int) -> None:
                normalized = name.strip().lower()
                if normalized in seen:
                    return
                seen.add(normalized)
                db.add(
                    CarrierZoneCity(
                        carrier_id=carrier.id,
                        city_name=name.strip().title(),
                        city_name_normalized=normalized,
                        zone=zone,
                        city_type="regional" if zone == 1 else "district",
                    )
                )

            # Regional centers → zone 1
            for city in REGIONAL_CENTERS:
                add_city(city, 1)
                cities_added += 1

            # District centers → zone 2
            for city in DISTRICT_CENTERS:
                add_city(city, 2)
                cities_added += 1

            db.flush()
            log.info("Zone cities added: %d", cities_added)

        db.commit()
        log.info("Seed complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.error("Seed failed: %s", exc)
        sys.exit(1)
