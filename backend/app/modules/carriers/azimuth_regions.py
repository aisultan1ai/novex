"""Azimuth /regions catalogue — model, repository, and lookup helpers.

Populated by:
  * scripts/sync_azimuth_regions.py — monthly cron pass over our seed cities
  * lazy on-demand fetches from `resolve_city()` when a user picks a city we
    have never seen before

Consumed by:
  * tariff_engine — filter out Azimuth from quotes when the route is not
    covered on origin AND destination, and derive zone number from real data
    instead of the hardcoded zone_mapper set
  * AzimuthAPIClient — normalise city names before sending to /invoices and
    /order-courier so we send the exact `title` Azimuth returned to us

See docs on the columns in migration 037.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    SmallInteger,
    String,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base

logger = logging.getLogger(__name__)


class AzimuthRegion(Base):
    __tablename__ = "azimuth_regions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    azimuth_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    zone: Mapped[str] = mapped_column(String(10), nullable=False)
    zone_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_origin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_destination: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)


# ── Normalisation ─────────────────────────────────────────────────────────────

# Alt-names our users might type in Latin / Kazakh where Azimuth catalogues the
# Russian form. Extend as we notice new mismatches during lazy learning.
_TITLE_ALIASES: dict[str, str] = {
    "оскемен": "усть-каменогорск",
    "oskemen": "усть-каменогорск",
    "нур-султан": "астана",
    "нурсултан": "астана",
    "almaty": "алматы",
    "alma-ata": "алматы",
    "алма-ата": "алматы",
    "astana": "астана",
    "shymkent": "шымкент",
    "aktobe": "актобе",
    "karaganda": "караганда",
}


def normalize_title(city: str) -> str:
    """Lower + strip + collapse whitespace → the lookup key.

    Aliases like "Оскемен" → "усть-каменогорск" are applied so that user input
    resolves to the exact title Azimuth uses in their catalogue.
    """
    s = (city or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return _TITLE_ALIASES.get(s, s)


def _parse_zone_number(zone: str) -> int:
    """`kz_1` → 1, `kz_2` → 2, `kz_3` → 3. Unknown → 3 (safest, priciest)."""
    m = re.search(r"(\d+)", zone or "")
    return int(m.group(1)) if m else 3


# ── Repository ────────────────────────────────────────────────────────────────


class AzimuthRegionsRepository:
    def find(
        self,
        db: Session,
        city: str,
        *,
        direction: str,
    ) -> AzimuthRegion | None:
        """Look up a region by user-typed city name.

        direction: 'origin' → row must have is_origin=True
                   'destination' → row must have is_destination=True

        Returns the best match by:
          1. Exact (normalized) title match
          2. Prefer the row with the lowest zone_number (regional > district)
             so the customer gets the correct price for a well-known city
             when multiple villages share the same name.

        Falls back to None so the caller can trigger a lazy fetch or use the
        hardcoded zone_mapper fallback.
        """
        normalized = normalize_title(city)
        if not normalized:
            return None

        stmt = select(AzimuthRegion).where(
            AzimuthRegion.title_normalized == normalized
        )
        if direction == "origin":
            stmt = stmt.where(AzimuthRegion.is_origin.is_(True))
        elif direction == "destination":
            stmt = stmt.where(AzimuthRegion.is_destination.is_(True))
        else:
            raise ValueError(f"direction must be 'origin' or 'destination', got {direction!r}")

        stmt = stmt.order_by(AzimuthRegion.zone_number.asc()).limit(1)
        return db.scalar(stmt)

    def upsert_from_api(
        self,
        db: Session,
        items: list[dict[str, Any]],
        *,
        direction: str,
    ) -> tuple[int, int]:
        """Bulk-UPSERT rows from Azimuth's /regions response.

        `items` — list of {id, title, path, zone, origin, destination}.
        `direction` — which side of the request we saw, so we do NOT wipe the
        other side's flag on a merge (e.g. a destination-only pass must not
        set is_origin=False for cities that also appear as origins).

        Returns (inserted, updated) counts for logging.
        """
        if not items:
            return 0, 0

        rows: list[dict[str, Any]] = []
        for it in items:
            azid = it.get("id")
            title = (it.get("title") or "").strip()
            if not azid or not title:
                continue
            zone = str(it.get("zone") or "")
            rows.append({
                "azimuth_id": int(azid),
                "title": title[:255],
                "path": (it.get("path") or "")[:500],
                "zone": zone[:10],
                "zone_number": _parse_zone_number(zone),
                "is_origin": bool(it.get("origin", False)),
                "is_destination": bool(it.get("destination", False)),
                "title_normalized": normalize_title(title),
                "synced_at": datetime.utcnow(),
            })

        if not rows:
            return 0, 0

        # PG-specific UPSERT so we can preserve the "other" direction flag.
        # For a destination-side sync we OR-in is_destination but keep the
        # existing is_origin value from the row (excluded.is_origin=false
        # would otherwise unset it).
        stmt = pg_insert(AzimuthRegion.__table__).values(rows)

        update_cols: dict[str, Any] = {
            "title": stmt.excluded.title,
            "path": stmt.excluded.path,
            "zone": stmt.excluded.zone,
            "zone_number": stmt.excluded.zone_number,
            "title_normalized": stmt.excluded.title_normalized,
            "synced_at": stmt.excluded.synced_at,
        }
        if direction == "origin":
            # Merge origin, leave destination alone.
            update_cols["is_origin"] = stmt.excluded.is_origin
        elif direction == "destination":
            update_cols["is_destination"] = stmt.excluded.is_destination
        else:
            # Full sync (both flags authoritative).
            update_cols["is_origin"] = stmt.excluded.is_origin
            update_cols["is_destination"] = stmt.excluded.is_destination

        stmt = stmt.on_conflict_do_update(
            index_elements=["azimuth_id"],
            set_=update_cols,
        )
        db.execute(stmt)
        db.commit()
        return len(rows), 0  # We do not distinguish insert vs update here.

    def count(self, db: Session) -> int:
        from sqlalchemy import func
        return db.scalar(select(func.count()).select_from(AzimuthRegion)) or 0


# ── Public helpers ────────────────────────────────────────────────────────────


_repo = AzimuthRegionsRepository()


def resolve_city(
    db: Session,
    city: str,
    *,
    direction: str,
    creds: dict | None = None,
    lazy: bool = True,
) -> AzimuthRegion | None:
    """Resolve a user-typed city name to a stored Azimuth region row.

    On cache miss, if `lazy=True` and `creds` are provided, fires a single
    live GET to /regions?type={direction}&title={city}, persists the result,
    then re-queries. Suitable for the /shipping/quote path where we can
    afford an extra HTTP round-trip.

    For hot paths that must not block on network (e.g. bulk order dispatch)
    pass `lazy=False` — a None result will fall back to the hardcoded
    zone_mapper.
    """
    hit = _repo.find(db, city, direction=direction)
    if hit is not None or not lazy or not creds:
        return hit

    from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient

    try:
        raw = AzimuthAPIClient().search_regions(direction, city, creds)
    except Exception as exc:
        logger.warning("Azimuth lazy /regions fetch failed for %r: %s", city, exc)
        return None

    items = raw.get("data") or []
    if not items:
        return None

    _repo.upsert_from_api(db, items, direction=direction)
    return _repo.find(db, city, direction=direction)
