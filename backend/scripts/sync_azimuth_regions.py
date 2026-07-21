"""Sync azimuth_regions from Azimuth's live /regions catalogue.

Two modes:
  --mode seed       (default) — small pass over our hardcoded KZ cities
                    (~55 cities × 2 directions ≈ 110 requests). Fast, keeps
                    the table in sync for cities we care about.
  --mode full       Alphabet scan: two-letter prefixes (аа...яя + aa..zz)
                    for both directions. Long-running (~2000+ requests) but
                    catches everything Azimuth catalogues. Meant for the
                    monthly cron; sequential and rate-limited so we do not
                    hammer their API.

The API returns at most 30 rows per call and does not paginate, so a single
letter often truncates — two-letter prefixes are the minimum granularity that
avoids silent drops for common letters.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

logger = logging.getLogger("sync_azimuth_regions")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Seed = our hardcoded set from zone_mapper (both regional + district centres).
# Any city in this list should resolve on Azimuth's side; if it doesn't,
# something drifted and the operator sees it in the run summary.
SEED_CITIES: list[str] = [
    # regional centres
    "Актобе", "Алматы", "Астана", "Атырау", "Жезказган", "Караганда",
    "Кокшетау", "Костанай", "Кызылорда", "Усть-Каменогорск", "Павлодар",
    "Петропавловск", "Семей", "Талдыкорган", "Тараз", "Уральск",
    "Шымкент", "Актау",
    # district / smaller centres
    "Аксай", "Жанаозен", "Кульсары", "Экибастуз", "Степногорск", "Рудный",
    "Лисаковск", "Аркалык", "Темиртау", "Балхаш", "Саран", "Шахтинск",
    "Сарыагаш", "Арыс", "Кентау", "Туркестан", "Жанакорган", "Риддер",
    "Зыряновск", "Курчатов", "Абай", "Приозерск", "Щучинск", "Бурабай",
    "Аксу", "Капшагай", "Конаев", "Каскелен", "Талгар", "Есик",
    "Жаркент", "Текели",
]


def _iter_two_letter_prefixes() -> list[str]:
    """а..я × а..я + a..z × a..z."""
    cyr = "абвгдежзийклмнопрстуфхцчшщъыьэюя"
    lat = "abcdefghijklmnopqrstuvwxyz"
    return [a + b for a in cyr for b in cyr] + [a + b for a in lat for b in lat]


def _sync_titles(
    titles: list[str],
    *,
    directions: tuple[str, ...],
    sleep_ms: int,
) -> tuple[int, int, int]:
    """Fetch each (title, direction) and upsert. Returns (calls, rows_seen, empty)."""
    from app.core.db import SessionLocal
    from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient
    from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
    from app.modules.carriers.azimuth_regions import AzimuthRegionsRepository

    with SessionLocal() as db:
        cred_row = CarrierAPICredentialsRepository().get_by_carrier_code(db, "azimuth")
        if not cred_row or not cred_row.is_active:
            logger.error("No active Azimuth credentials. Aborting.")
            return 0, 0, 0
        creds = {
            "api_url": cred_row.api_url,
            "api_token": cred_row.api_token,
            **(cred_row.extra_config or {}),
        }

    client = AzimuthAPIClient()
    repo = AzimuthRegionsRepository()

    calls = rows_seen = empty = 0
    delay = sleep_ms / 1000 if sleep_ms > 0 else 0.0

    for title in titles:
        for direction in directions:
            calls += 1
            try:
                raw = client.search_regions(direction, title, creds)
            except Exception as exc:
                logger.warning("call %s/%s failed: %s", direction, title, exc)
                if delay:
                    time.sleep(delay)
                continue

            items = raw.get("data") or []
            if not items:
                empty += 1
            else:
                rows_seen += len(items)
                # Every call opens+commits its own short session so a hung sync
                # never holds a connection for the whole run.
                from app.core.db import SessionLocal as _SL
                with _SL() as db:
                    repo.upsert_from_api(db, items, direction=direction)

            if delay:
                time.sleep(delay)

        if calls % 50 == 0:
            logger.info("progress: %s calls, %s rows seen, %s empty", calls, rows_seen, empty)

    return calls, rows_seen, empty


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Azimuth regions into local DB.")
    parser.add_argument(
        "--mode",
        choices=("seed", "full"),
        default="seed",
        help="'seed' = ~55 hardcoded KZ cities; 'full' = alphabet scan (long).",
    )
    parser.add_argument(
        "--directions",
        default="both",
        choices=("origin", "destination", "both"),
        help="Which side(s) to fetch. Defaults to both.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=100,
        help="Pause between calls in ms to avoid hammering the Azimuth API.",
    )
    args = parser.parse_args()

    if args.mode == "seed":
        titles = SEED_CITIES
    else:
        titles = _iter_two_letter_prefixes()

    if args.directions == "both":
        directions: tuple[str, ...] = ("origin", "destination")
    else:
        directions = (args.directions,)

    logger.info(
        "Starting Azimuth regions sync: mode=%s titles=%d directions=%s sleep=%dms",
        args.mode, len(titles), directions, args.sleep_ms,
    )
    calls, rows, empty = _sync_titles(titles, directions=directions, sleep_ms=args.sleep_ms)

    from app.core.db import SessionLocal
    from app.modules.carriers.azimuth_regions import AzimuthRegionsRepository
    with SessionLocal() as db:
        total = AzimuthRegionsRepository().count(db)

    logger.info(
        "Done. calls=%d rows_seen=%d empty=%d table_total=%d",
        calls, rows, empty, total,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
