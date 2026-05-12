from __future__ import annotations

# Maps carrier-specific status codes to internal Novex statuses.
CARRIER_STATUS_MAP: dict[str, str] = {
    "PICKED_UP": "picked_up",
    "IN_TRANSIT": "in_transit",
    "OUT_FOR_DELIVERY": "out_for_delivery",
    "DELIVERED": "delivered",
    "FAILED_ATTEMPT": "delivery_failed",
    "RETURNED": "returned",
    "CUSTOMS_HOLD": "customs_hold",
}


def map_carrier_status(carrier_status: str) -> str:
    return CARRIER_STATUS_MAP.get(carrier_status.upper(), "in_transit")
