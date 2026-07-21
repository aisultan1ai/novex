"""Probe Azimuth's GET /api/integration/regions/{type} endpoint.

Read-only. Reads live Azimuth credentials from the local carrier_api_credentials
table, then makes 1..N GET calls to Azimuth and pretty-prints the raw JSON so we
can design a proper local storage schema for their region catalogue.

Usage:
    python -m scripts.probe_azimuth_regions --title Алматы
    python -m scripts.probe_azimuth_regions --title Астана --type destination
    python -m scripts.probe_azimuth_regions --title Алматы --both  # origin + destination
    python -m scripts.probe_azimuth_regions --sample                # curated sample list

Nothing is written back to Azimuth or to our DB — this script is pure inspect.
"""
from __future__ import annotations

import argparse
import json
import sys

# Small sample of KZ cities from our zone_mapper — useful for a quick pass to
# see which of our hardcoded cities Azimuth actually accepts.
SAMPLE_CITIES = [
    "Алматы",
    "Астана",
    "Шымкент",
    "Караганда",
    "Актобе",
    "Атырау",
    "Оскемен",
    "Павлодар",
    "Тараз",
    "Кызылорда",
    "Актау",
    "Рудный",
    "Экибастуз",
    "Аксай",
    "Талгар",  # district-center, edge case
    "НекогоТакогоГорода",  # sanity check that Azimuth returns [] for garbage
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Azimuth /regions endpoint")
    parser.add_argument("--title", help="City name / substring to search")
    parser.add_argument(
        "--type",
        choices=("origin", "destination"),
        default="origin",
        help="Region direction (default: origin)",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Query both origin and destination for the given title",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help=(
            "Iterate through a curated sample of KZ cities. Uses --type unless "
            "--both is also passed."
        ),
    )
    args = parser.parse_args()

    if not args.title and not args.sample:
        parser.error("either --title or --sample is required")

    # Bootstrap the app: DB session + Azimuth creds.
    from app.core.db import SessionLocal
    from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient
    from app.modules.carriers.api_credentials import CarrierAPICredentialsRepository

    with SessionLocal() as db:
        row = CarrierAPICredentialsRepository().get_by_carrier_code(db, "azimuth")
        if not row:
            print("ERROR: no CarrierAPICredentials row for carrier_code='azimuth'.")
            print("       Configure Azimuth API creds in the admin UI first.")
            return 2
        if not row.is_active:
            print("ERROR: Azimuth credentials exist but is_active=False. Enable them first.")
            return 2
        creds = {
            "api_url": row.api_url,
            "api_token": row.api_token,
            **(row.extra_config or {}),
        }

    client = AzimuthAPIClient()
    titles = SAMPLE_CITIES if args.sample else [args.title]
    types = ("origin", "destination") if args.both else (args.type,)

    for title in titles:
        for t in types:
            print(f"\n══════ type={t} title={title!r} ══════")
            try:
                data = client.search_regions(t, title, creds)
            except Exception as exc:
                print(f"  ERROR: {exc}")
                continue
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
