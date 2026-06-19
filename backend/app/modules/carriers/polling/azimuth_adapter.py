from __future__ import annotations

import logging

import httpx

from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData

logger = logging.getLogger(__name__)

# Azimuth tracking API endpoint — update when Azimuth grants API access.
# Fallback option: HTML scraping via https://azimuth.kz/ru/tracking/{number}
_TRACKING_URL = "https://api.azimuth.kz/tracking/{tracking_number}"

_STATUS_MAP: dict[str, str] = {
    "ACCEPTED": "picked_up",
    "IN_TRANSIT": "in_transit",
    "ARRIVED": "arrived",
    "OUT_FOR_DELIVERY": "in_transit",
    "DELIVERED": "delivered",
    "RETURNED": "returned",
    "CANCELLED": "cancelled",
}


class AzimuthAdapter(CarrierPollingAdapter):
    carrier_code = "azimuth"

    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        # No live API credentials yet — returns empty list until Azimuth merchant
        # onboarding is complete and _TRACKING_URL is confirmed.
        return []

        # Reference implementation for when API access is available:
        # try:
        #     resp = httpx.get(
        #         _TRACKING_URL.format(tracking_number=tracking_number),
        #         timeout=10,
        #     )
        #     resp.raise_for_status()
        #     events = resp.json().get("events", [])
        #     return [
        #         TrackingEventData(
        #             status=_STATUS_MAP.get(e.get("status", "").upper(), "in_transit"),
        #             carrier_status=e.get("status", ""),
        #             location=e.get("location"),
        #             description=e.get("description"),
        #             occurred_at=datetime.fromisoformat(e["timestamp"]),
        #         )
        #         for e in events
        #     ]
        # except Exception as exc:
        #     logger.warning("AzimuthAdapter fetch_status failed: %s", exc)
        #     raise
