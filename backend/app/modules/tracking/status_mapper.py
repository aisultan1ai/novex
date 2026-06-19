from __future__ import annotations

# Generic status map for carriers that use Novex webhook protocol.
CARRIER_STATUS_MAP: dict[str, str] = {
    "PICKED_UP": "picked_up",
    "IN_TRANSIT": "in_transit",
    "OUT_FOR_DELIVERY": "out_for_delivery",
    "DELIVERED": "delivered",
    "FAILED_ATTEMPT": "delivery_failed",
    "RETURNED": "returned",
    "CUSTOMS_HOLD": "customs_hold",
    # Exline (MeaSoft Courier) statuses
    "NEW": "sent_to_carrier",
    "ACCEPTED": "picked_up",
    "DELIVERY": "in_transit",
    "COMPLETE": "delivered",
    "CANCELED": "cancelled",
    "RETURN": "return_in_progress",
    # Azimuth statuses
    "ARRIVED": "arrived",
    "CANCELLED": "cancelled",
}

# Per-carrier overrides for codes that conflict between carriers.
_CARRIER_OVERRIDES: dict[str, dict[str, str]] = {}


def map_carrier_status(carrier_status: str, carrier_code: str | None = None) -> str:
    key = carrier_status.upper()
    if carrier_code:
        override = _CARRIER_OVERRIDES.get(carrier_code, {})
        if key in override:
            return override[key]
    return CARRIER_STATUS_MAP.get(key, "in_transit")
