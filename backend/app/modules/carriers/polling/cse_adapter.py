from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData

logger = logging.getLogger(__name__)

# Map CSE status names → internal Novex statuses
_STATUS_MAP: dict[str, str] = {
    # Russian names from CSE system
    "принят":               "sent_to_carrier",
    "принято":              "sent_to_carrier",
    "поступил":             "sent_to_carrier",
    "забран":               "picked_up",
    "забрано":              "picked_up",
    "забор":                "picked_up",
    "в пути":               "in_transit",
    "в транзите":           "in_transit",
    "транзит":              "in_transit",
    "прибыл":               "in_transit",
    "прибыло":              "in_transit",
    "передан на доставку":  "in_transit",
    "вручено":              "delivered",
    "доставлено":           "delivered",
    "получено":             "delivered",
    "отказ":                "delivery_failed",
    "неудачная попытка":    "delivery_failed",
    "возврат":              "return_in_progress",
    "возвращено":           "return_in_progress",
    "отменено":             "cancelled",
    "аннулировано":         "cancelled",
}


def _map_status(carrier_status: str) -> str:
    normalized = carrier_status.strip().lower()
    for key, mapped in _STATUS_MAP.items():
        if key in normalized:
            return mapped
    return "in_transit"


def _parse_datetime(value: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now(UTC).replace(tzinfo=None)


class CSEPollingAdapter(CarrierPollingAdapter):
    """
    Tracking adapter for CSE (Courier Service Express).

    Credentials from CarrierAPICredentials.extra_config:
        login    — API login
        password — API password
    api_url from CarrierAPICredentials.api_url.
    Falls back to CSE_LOGIN / CSE_PASSWORD env vars if creds are empty.
    """

    carrier_code = "cse"

    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        from app.modules.carriers.api_clients.cse import DEFAULT_API_URL, CSEAPIClient

        from app.core.config import get_settings as _get_settings
        _s = _get_settings()
        login = creds.get("login") or _s.cse_login
        password = creds.get("password") or _s.cse_password
        api_url = creds.get("api_url") or _s.cse_api_url or DEFAULT_API_URL

        if not login:
            logger.warning(
                "CSEPollingAdapter: no credentials for tracking (waybill=%s)", tracking_number
            )
            return []

        effective_creds = {"login": login, "password": password, "api_url": api_url}
        client = CSEAPIClient()

        try:
            raw_events = client.tracking(tracking_number, effective_creds)
        except Exception as exc:
            logger.warning(
                "CSEPollingAdapter: tracking request failed (waybill=%s): %s",
                tracking_number, exc,
            )
            raise

        events: list[TrackingEventData] = []
        for ev in raw_events:
            carrier_status = ev.get("status", "")
            occurred_at = _parse_datetime(ev.get("occurred_at", ""))
            mapped = _map_status(carrier_status)
            events.append(TrackingEventData(
                status=mapped,
                carrier_status=carrier_status,
                location=ev.get("location") or None,
                occurred_at=occurred_at,
                description=ev.get("comment") or carrier_status or None,
            ))

        logger.debug(
            "CSEPollingAdapter: %d events for waybill=%s", len(events), tracking_number
        )
        return events
