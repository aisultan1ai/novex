"""Azimuth tracking adapter — GET /api/integration/waybills/follow.

Called by the polling scheduler once per active Azimuth shipment. Azimuth's
`follow` endpoint returns the full history in one shot (no incremental cursor),
so we translate every parcels[].tracks[] entry into a TrackingEventData and let
the scheduler dedup by (carrier_status, occurred_at) on the way in.

Status mapping approach:
  * Prefer the two-letter `code` field (`pn`, `ls`, ...) when it appears in
    _CODE_MAP — codes are stable across languages.
  * Fall back to substring match on `description` (Russian) for the many
    codes Azimuth does not document (some appear as free-form Russian).
  * Anything still unmapped returns "carrier_unknown". This is NOT in the
    order state machine, so `can_transition(order.status, "carrier_unknown")`
    is always False and the scheduler leaves order.status alone — same
    safety net we added for CSE. Raw carrier_status (description or code)
    is still persisted on TrackingEvent so the customer sees the timeline.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from app.common.log_ratelimit import log_once_per
from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData

logger = logging.getLogger(__name__)

_TIMEOUT = 15

# ── Status maps ────────────────────────────────────────────────────────────

# Two-letter codes from parcels[].tracks[].code. Extend as new codes appear
# in the field — Azimuth does not publish a full list, so this grows via
# observed events (see the warning log at the bottom of _map_track).
_CODE_MAP: dict[str, str] = {
    "pn": "sent_to_carrier",  # Регистрация в системе
    "ls": "delivered",        # Успешная доставка
    # Below: educated defaults for codes we have not seen yet. Comment out
    # or correct once we observe a mismatch in prod.
    # "ph": "picked_up",      # предполож. приём курьером
    # "tr": "in_transit",     # предполож. в транзите
    # "ar": "arrived",        # предполож. прибыл в пункт выдачи
    # "od": "out_for_delivery",
    # "rt": "returned",
    # "cn": "cancelled",
}

# Substring match on the human-readable description (Russian). More specific
# phrases MUST come first — the first substring hit wins. Same pattern as
# CSE adapter's _STATUS_MAP.
_DESCRIPTION_MAP: dict[str, str] = {
    "успешная доставка":        "delivered",
    "доставлено":               "delivered",
    "доставлен":                "delivered",
    "вручено":                  "delivered",
    "вручен":                   "delivered",
    "передан на доставку":      "out_for_delivery",
    "передан курьеру":          "out_for_delivery",
    "выехал на доставку":       "out_for_delivery",
    "прибыл в пункт":           "arrived",
    "прибыло в пункт":          "arrived",
    "на складе назначения":     "arrived",
    "готов к выдаче":           "arrived",
    "прибыл в город":           "arrived",
    "в пути":                   "in_transit",
    "в транзите":               "in_transit",
    "транзит":                  "in_transit",
    "отгружен":                 "in_transit",
    "отправлен":                "in_transit",
    "забор":                    "picked_up",
    "забран":                   "picked_up",
    "принят на склад":          "picked_up",
    "регистрация в системе":    "sent_to_carrier",
    "принят":                   "sent_to_carrier",
    "оформлен":                 "sent_to_carrier",
    "отказ":                    "delivery_failed",
    "не доставлен":             "delivery_failed",
    "возврат":                  "return_in_progress",
    "отменено":                 "cancelled",
    "отменен":                  "cancelled",
    "аннулировано":             "cancelled",
}

# Terminal deliveries[].status from the top level of the response. Independent
# of parcels[].tracks — Azimuth writes here when the courier closes out the
# delivery leg. `success` is the only value we have seen so far; `failed` and
# `refused` inferred from their `code` values.
_DELIVERY_STATUS_MAP: dict[str, str] = {
    "success":  "delivered",
    "failed":   "delivery_failed",
    "refused":  "delivery_failed",
    "returned": "return_in_progress",
    "cancelled": "cancelled",
}

_UNKNOWN_STATUS = "carrier_unknown"


def _map_track(code: str, description: str) -> str:
    """code + description → internal status; unknown → carrier_unknown."""
    if code:
        mapped = _CODE_MAP.get(code.strip().lower())
        if mapped:
            return mapped

    normalized = (description or "").strip().lower()
    if normalized:
        for phrase, mapped in _DESCRIPTION_MAP.items():
            if phrase in normalized:
                return mapped

    # Rate-limited: mass polling would otherwise log this for every unknown
    # event on every tick. Key on (code, description) so a genuinely new code
    # still surfaces once per TTL window.
    log_once_per(
        logger,
        f"azimuth-unmapped:{code!r}:{(description or '').strip().lower()!r}",
        "AzimuthAdapter: unmapped tracking event code=%r description=%r "
        "→ keeping order status unchanged",
        code, description,
    )
    return _UNKNOWN_STATUS


def _parse_datetime(value: str) -> datetime:
    """Azimuth returns ISO-8601 with microseconds and Z suffix.

    Fallback to now() only if the input is unparseable — event dedup uses
    occurred_at as part of the key, so an unparseable date collapses multiple
    events into the same "now" bucket. Log so we can tighten the parser.

    Truncated to whole seconds: dedup in the polling scheduler compares
    occurred_at equality across all adapters, and CSE / Exline emit
    second-precision timestamps. Keeping microseconds here would cause the
    same Azimuth event to look "new" whenever the fallback branch fired,
    since two `now()` calls a millisecond apart would not collide.
    """
    if not value:
        return datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    raw = value.strip()
    # Handle "2021-01-05T09:42:38.278000Z" and variants.
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        logger.debug("AzimuthAdapter: unparseable date %r, falling back to now()", value)
        return datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    # Store naive UTC to match every other adapter — TrackingEvent.occurred_at
    # is a TIMESTAMP WITHOUT TIME ZONE column.
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.replace(microsecond=0)


class AzimuthAdapter(CarrierPollingAdapter):
    """Tracking adapter for Azimuth Cargo.

    Credentials from CarrierAPICredentials:
        api_url    — base URL, e.g. https://api.azimuthcargo.kz
        api_token  — Bearer token
    """

    carrier_code = "azimuth"

    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        api_url = str(creds.get("api_url") or "").rstrip("/")
        token = str(creds.get("api_token") or "")
        if not api_url or not token:
            logger.warning(
                "AzimuthAdapter: missing credentials (api_url=%s token_set=%s) "
                "— cannot poll waybill=%s",
                bool(api_url), bool(token), tracking_number,
            )
            return []

        try:
            resp = httpx.get(
                f"{api_url}/api/integration/waybills/follow",
                params={"waybill": tracking_number},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    # Force Laravel to return JSON error bodies instead of an
                    # HTML login redirect when auth expires.
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=_TIMEOUT,
            )
        except Exception as exc:
            logger.warning(
                "AzimuthAdapter: /waybills/follow request failed waybill=%s: %s",
                tracking_number, exc,
            )
            raise

        # 422 with message "Waybill does not exist" is Azimuth's way of saying
        # "not indexed yet" — normal right after dispatch when the waybill has
        # been created but their internal state hasn't propagated. Return no
        # events; scheduler will just try again next tick.
        if resp.status_code == 422:
            logger.debug(
                "AzimuthAdapter: waybill=%s not indexed yet (422): %s",
                tracking_number, (resp.text or "")[:200],
            )
            return []
        if resp.status_code >= 400:
            body_preview = (resp.text or "")[:400]
            raise RuntimeError(
                f"Azimuth /waybills/follow вернул {resp.status_code}: {body_preview}"
            )

        try:
            body = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"Azimuth /waybills/follow: невалидный JSON: {(resp.text or '')[:200]}"
            ) from exc

        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            logger.debug(
                "AzimuthAdapter: unexpected body shape for waybill=%s: %s",
                tracking_number, str(body)[:400],
            )
            return []

        events: list[TrackingEventData] = []
        seen_statuses: set[str] = set()

        # 1) Per-parcel tracks — the granular event stream.
        for parcel in data.get("parcels") or []:
            for track in parcel.get("tracks") or []:
                code = str(track.get("code") or "")
                description = str(track.get("description") or "").strip()
                carrier_status = description or code or "unknown"
                mapped = _map_track(code, description)
                events.append(TrackingEventData(
                    status=mapped,
                    carrier_status=carrier_status,
                    location=(track.get("location_full") or track.get("location") or None),
                    occurred_at=_parse_datetime(str(track.get("created_at") or "")),
                    description=description or None,
                ))
                seen_statuses.add(mapped)

        # 2) Top-level deliveries[] — terminal leg (success / failed / refused).
        # Azimuth almost always duplicates the "Успешная доставка" track here
        # with a *different* timestamp (admin close-out vs courier scan), which
        # slips past the (carrier_status, occurred_at) dedup and shows the
        # customer two "Доставлен" cards. Skip if we already have that mapped
        # status from tracks[]; keep the entry only when it introduces a new
        # terminal signal (e.g. `refused` when tracks[] has no such event).
        for delivery in data.get("deliveries") or []:
            status_str = str(delivery.get("status") or "").lower().strip()
            mapped = _DELIVERY_STATUS_MAP.get(status_str, _UNKNOWN_STATUS)
            if mapped in seen_statuses:
                continue
            description = str(delivery.get("description") or "").strip()
            carrier_status = description or f"delivery:{status_str}" or "delivery"
            events.append(TrackingEventData(
                status=mapped,
                carrier_status=carrier_status,
                location=None,
                occurred_at=_parse_datetime(str(delivery.get("date") or "")),
                description=(
                    delivery.get("notes")
                    or delivery.get("receiver_position")
                    or description
                    or None
                ),
            ))
            seen_statuses.add(mapped)

        logger.debug(
            "AzimuthAdapter: %d events for waybill=%s", len(events), tracking_number
        )
        return events
