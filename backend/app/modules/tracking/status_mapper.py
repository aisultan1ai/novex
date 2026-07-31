from __future__ import annotations

import logging

from app.common.log_ratelimit import log_once_per

logger = logging.getLogger(__name__)

# Generic status map for carriers that push via Novex webhook protocol.
# Отдельные адаптеры (Azimuth/CSE/Exline) держат СВОИ более полные карты в
# app.modules.carriers.polling.*_adapter — здесь только то, что реально
# может прийти через POST /carrier-tracking, т.е. подмножество базовых кодов.
CARRIER_STATUS_MAP: dict[str, str] = {
    # ── Стандартный Novex webhook протокол ─────────────────────────────
    "PICKED_UP":        "picked_up",
    "IN_TRANSIT":       "in_transit",
    "OUT_FOR_DELIVERY": "out_for_delivery",
    "DELIVERED":        "delivered",
    "FAILED_ATTEMPT":   "delivery_failed",
    "RETURNED":         "returned",
    "CUSTOMS_HOLD":     "customs_hold",

    # ── Exline (MeaSoft) — если shorlist приходит через webhook, а не
    # polling. Полный enum (31 значение) — в exline_adapter._STATUS_MAP.
    # Semantic fix: ACCEPTED — это «получен складом», НЕ забор; DELIVERY —
    # «выдан курьеру», НЕ транзит между складами.
    "NEW":              "sent_to_carrier",
    "ACCEPTED":         "in_transit",
    "PICKUP":           "picked_up",
    "DELIVERY":         "out_for_delivery",
    "COMPLETE":         "delivered",
    "CANCELED":         "cancelled",

    # ── Azimuth ────────────────────────────────────────────────────────
    "ARRIVED":          "arrived",
    "CANCELLED":        "cancelled",
}

# Per-carrier overrides for codes that conflict between carriers.
_CARRIER_OVERRIDES: dict[str, dict[str, str]] = {}


def map_carrier_status(carrier_status: str, carrier_code: str | None = None) -> str:
    """Webhook carrier status → internal Novex status.

    Unknown → 'carrier_unknown' (safe: не в state machine, can_transition
    вернёт False и статус заказа не двинется). Раньше здесь был silent
    fallback на 'in_transit' — тот же баг, от которого ушли в CSE/Exline:
    неизвестный webhook payload переводил заказ в 'В пути' без warning'а.
    """
    key = (carrier_status or "").upper()
    if carrier_code:
        override = _CARRIER_OVERRIDES.get(carrier_code, {})
        if key in override:
            return override[key]
    mapped = CARRIER_STATUS_MAP.get(key)
    if mapped:
        return mapped
    log_once_per(
        logger,
        f"webhook-unmapped:{carrier_code or 'any'}:{key}",
        "Unmapped webhook status carrier=%r status=%r → carrier_unknown",
        carrier_code, carrier_status,
    )
    return "carrier_unknown"
