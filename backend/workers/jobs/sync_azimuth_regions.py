"""Periodic sync of azimuth_regions from Azimuth's /regions catalogue.

Wraps the standalone `scripts/sync_azimuth_regions.py` "seed" pass as a
scheduled job so the worker keeps our local city cache fresh without an
operator running the CLI. See migration 037 + azimuth_regions.py.

Interval: 7 days. Seed mode is ~110 GETs (55 cities × origin+destination)
and completes in ~15 seconds — safe to run inside the shared worker loop.

Redis lock keeps multi-replica deployments from double-syncing.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

_LOCK_KEY = "lock:sync_azimuth_regions"
# Lock long enough to cover a slow sync (network variance) but short enough
# that a crashed worker does not silently skip the next scheduled run.
_LOCK_TTL = 15 * 60  # 15 minutes


# Same list as scripts/sync_azimuth_regions.py::SEED_CITIES. Kept in-sync by
# convention — if new cities are added there, mirror them here (or vice
# versa). Duplicated intentionally rather than importing a script module,
# which is not part of the app package and does not ship in the worker image
# in all deploy layouts.
_SEED_CITIES: list[str] = [
    "Актобе", "Алматы", "Астана", "Атырау", "Жезказган", "Караганда",
    "Кокшетау", "Костанай", "Кызылорда", "Усть-Каменогорск", "Павлодар",
    "Петропавловск", "Семей", "Талдыкорган", "Тараз", "Уральск",
    "Шымкент", "Актау",
    "Аксай", "Жанаозен", "Кульсары", "Экибастуз", "Степногорск", "Рудный",
    "Лисаковск", "Аркалык", "Темиртау", "Балхаш", "Саран", "Шахтинск",
    "Сарыагаш", "Арыс", "Кентау", "Туркестан", "Жанакорган", "Риддер",
    "Зыряновск", "Курчатов", "Абай", "Приозерск", "Щучинск", "Бурабай",
    "Аксу", "Капшагай", "Конаев", "Каскелен", "Талгар", "Есик",
    "Жаркент", "Текели",
]


def run(db: Session) -> None:
    r = get_redis()
    if not r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL):
        logger.debug("sync_azimuth_regions: skipped — another replica holds the lock")
        return
    try:
        _sync(db)
    finally:
        r.delete(_LOCK_KEY)


def _sync(db: Session) -> None:
    from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient
    from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository
    from app.modules.carriers.azimuth_regions import AzimuthRegionsRepository

    cred_row = CarrierAPICredentialsRepository().get_by_carrier_code(db, "azimuth")
    if not cred_row or not cred_row.is_active:
        logger.warning("sync_azimuth_regions: no active Azimuth credentials — skipping")
        return
    creds = {
        "api_url": cred_row.api_url,
        "api_token": cred_row.api_token,
        **(cred_row.extra_config or {}),
    }

    client = AzimuthAPIClient()
    repo = AzimuthRegionsRepository()

    calls = rows = empty = 0
    t0 = time.time()
    for title in _SEED_CITIES:
        for direction in ("origin", "destination"):
            calls += 1
            try:
                raw = client.search_regions(direction, title, creds)
            except Exception as exc:
                logger.warning("sync_azimuth_regions: %s/%s failed: %s", direction, title, exc)
                continue

            items = raw.get("data") or []
            if not items:
                empty += 1
                continue
            rows += len(items)
            repo.upsert_from_api(db, items, direction=direction)
            # upsert_from_api commits internally; no additional flush needed.

            # Small pause between calls to avoid hammering the shared Azimuth
            # API during business hours.
            time.sleep(0.1)

    logger.info(
        "sync_azimuth_regions done: calls=%d rows_seen=%d empty=%d elapsed=%.1fs",
        calls, rows, empty, time.time() - t0,
    )
