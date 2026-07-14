from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData

logger = logging.getLogger(__name__)

# Map CSE status names → internal Novex statuses.
#
# `_map_status` picks the FIRST key whose substring appears in the CSE
# status string. Order matters: put SPECIFIC phrases before shorter
# generic ones. Example: "прибыл в пункт выдачи" must come before "прибыл",
# otherwise the short key would match first and short-circuit to arrived
# for every "прибыл*" event including transit hops.
_STATUS_MAP: dict[str, str] = {
    # ── Registered with carrier (paperwork done, not yet picked up) ────────
    "оформлен":                     "sent_to_carrier",
    "принят":                       "sent_to_carrier",
    "принято":                      "sent_to_carrier",
    "поступил":                     "sent_to_carrier",

    # ── Courier picked it up at the sender ────────────────────────────────
    "забран":                       "picked_up",
    "забрано":                      "picked_up",
    "забор":                        "picked_up",

    # ── At destination pickup point, waiting for recipient (arrived) ──────
    # Specific phrases go first so they win over the shorter "прибыл" below.
    "прибыл в пункт выдачи":        "arrived",
    "прибыл в пвз":                 "arrived",
    "прибыл в город":               "arrived",
    "прибыло в город":              "arrived",
    "на складе назначения":         "arrived",
    "в пункте выдачи":              "arrived",
    "готов к выдаче":               "arrived",
    "готов к получению":            "arrived",
    "ожидает получения":            "arrived",
    "ожидает получателя":           "arrived",

    # ── Out for delivery (courier is on the way to the recipient) ─────────
    "передан на доставку":          "out_for_delivery",
    "передан курьеру для доставки": "out_for_delivery",
    "выехал на доставку":           "out_for_delivery",
    "выезд на доставку":            "out_for_delivery",
    "курьер выехал":                "out_for_delivery",
    "курьер в пути":                "out_for_delivery",

    # ── In transit between warehouses ─────────────────────────────────────
    "в пути":                       "in_transit",
    "в транзите":                   "in_transit",
    "транзит":                      "in_transit",
    "отправлен":                    "in_transit",
    "отгружен":                     "in_transit",

    # Bare "прибыл" without context — treated as arrived (client-facing:
    # more informative than a generic "in_transit"). Placed AFTER all
    # specific "прибыл ..." keys so those win when applicable.
    "прибыл":                       "arrived",
    "прибыло":                      "arrived",

    # ── Delivered ─────────────────────────────────────────────────────────
    "вручено":                      "delivered",
    "вручен":                       "delivered",
    "доставлено":                   "delivered",
    "доставлен":                    "delivered",
    "получено":                     "delivered",
    "выдано":                       "delivered",

    # ── Delivery attempt failed ──────────────────────────────────────────
    "отказ":                        "delivery_failed",
    "неудачная попытка":            "delivery_failed",
    "не доставлен":                 "delivery_failed",

    # ── Return ────────────────────────────────────────────────────────────
    "возврат":                      "return_in_progress",
    "возвращено":                   "return_in_progress",
    "возвращается":                 "return_in_progress",

    # ── Cancelled ─────────────────────────────────────────────────────────
    "отменено":                     "cancelled",
    "отменен":                      "cancelled",
    "аннулировано":                 "cancelled",
}


def _map_status(carrier_status: str) -> str:
    normalized = carrier_status.strip().lower()
    for key, mapped in _STATUS_MAP.items():
        if key in normalized:
            return mapped
    # Unknown status — log so we can extend _STATUS_MAP when new phrasings
    # appear in prod. Fallback keeps the order visible in the tracking UI.
    logger.warning("CSEPollingAdapter: unmapped carrier status %r → in_transit (fallback)", carrier_status)
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
