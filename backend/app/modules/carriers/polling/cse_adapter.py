from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from app.common.log_ratelimit import log_once_per
from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData

logger = logging.getLogger(__name__)

# Map CSE status names → internal Novex statuses.
#
# `_map_status` picks the FIRST key whose substring appears in the CSE
# status string (case-insensitive). Order matters: put SPECIFIC phrases
# before shorter generic ones. Two rules to keep straight:
#
#   1. "отказ" must come before "отправлен", иначе "Отказ в приеме
#      отправления" получит in_transit вместо delivery_failed.
#   2. "доставл" must come before "отправлен", иначе "Отправление
#      доставлено" получит in_transit.
#
# Список пополняется по факту прогона живого CargoStates:
#   backend/scripts/sync_carrier_states.py
# — раз в месяц запустите и сверьте новые фразы.
_STATUS_MAP: dict[str, str] = {
    # ── Cancelled (проверяем ПЕРВЫМ: "Отмена заказа", "Отменён клиентом",
    # "Запрос на отмену", "Аннулировано" — все хотим ловить до "отправлен"
    # и "заказ"). ────────────────────────────────────────────────────────
    "отмена":                       "cancelled",
    "отменен":                      "cancelled",
    "отменён":                      "cancelled",
    "отменено":                     "cancelled",
    "аннулировано":                 "cancelled",
    "запрос на отмену":             "cancelled",

    # ── Customs — таможня приоритетнее любых "отправлен/груз в пути". ────
    "таможенном оформлении":        "customs_hold",
    "таможне":                      "customs_hold",
    "таможенн":                     "customs_hold",
    "перевозка/таможня":            "customs_hold",

    # ── Delivered — специфичные фразы ПЕРЕД общим "доставлен", а те до
    # "отправлен", чтобы "Отправление доставлено" ловилось верно. ─────────
    "доставка успешно выполнена":   "delivered",
    "доставка завершена":           "delivered",
    "груз передан клиенту":         "delivered",
    "отправление доставлено":       "delivered",
    "доставлено инициатору":        "delivered",
    "вручено":                      "delivered",
    "вручен":                       "delivered",
    "доставлено":                   "delivered",
    "доставлен":                    "delivered",
    "выдано":                       "delivered",
    "выдан получателю":             "delivered",

    # ── Delivery failed — "отказ" ЛОВИМ раньше "отправлен". Также
    # включаем: истёк срок хранения, попытки исчерпаны, утеряно/утилизация. ─
    "отказ":                        "delivery_failed",
    "неудачная попытка":            "delivery_failed",
    "не доставлен":                 "delivery_failed",
    "вручение отправления невозможно": "delivery_failed",
    "истек срок хранения":          "delivery_failed",
    "истёк срок хранения":          "delivery_failed",
    "истекло количество попыток":   "delivery_failed",
    "не успели":                    "delivery_failed",
    "утерян":                       "delivery_failed",
    "утеряно":                      "delivery_failed",
    "утилизация":                   "delivery_failed",
    "невозможно принять":           "delivery_failed",
    "получатель не может принять":  "delivery_failed",
    "сбор не осуществлен":          "delivery_failed",
    "сбор невозможен":              "delivery_failed",

    # ── Return ────────────────────────────────────────────────────────────
    "возврат отправителю":          "return_in_progress",
    "возврат инициатору":           "return_in_progress",
    "возврат":                      "return_in_progress",
    "возвращено":                   "return_in_progress",
    "возвращается":                 "return_in_progress",
    "отправление изъято":           "return_in_progress",

    # ── Arrived at destination (перед "отправлен" и "прибыл") ─────────────
    "прибыл в пункт выдачи":        "arrived",
    "прибыл в пвз":                 "arrived",
    "прибыл в город":               "arrived",
    "прибыло в город":              "arrived",
    "поступил в город назначения":  "arrived",
    "на складе назначения":         "arrived",
    "в пункте выдачи":              "arrived",
    "ожидает в пункте выдачи":      "arrived",
    "готов к выдаче":               "arrived",
    "готов к получению":            "arrived",
    "ожидает получения":            "arrived",
    "ожидает получателя":           "arrived",
    "принят на пвз для доставки":   "arrived",
    "получатель самостоятельно заберет": "arrived",

    # ── Out for delivery (перед "отправлен") ─────────────────────────────
    "передан на доставку":          "out_for_delivery",
    "передан курьеру для доставки": "out_for_delivery",
    "выехал на доставку":           "out_for_delivery",
    "выезд на доставку":            "out_for_delivery",
    "курьер уже в пути":            "out_for_delivery",
    "курьер выехал":                "out_for_delivery",
    "курьер в пути":                "out_for_delivery",
    "ожидайте курьера":             "out_for_delivery",
    "груз выбыл из пвз":            "out_for_delivery",

    # ── Picked up (перед "отправлен" и "принят") ─────────────────────────
    "отправление получено курьером": "picked_up",
    "груз забран":                  "picked_up",
    "отправление забрано":          "picked_up",
    "забран":                       "picked_up",
    "забрано":                      "picked_up",

    # ── Registered with carrier — общее «принят/оформлен» (после cancel!)
    # 'Заказ подтвержден клиентом' / 'Заказ утвержден.' / 'Заказ проверяется.'
    # / 'Назначен курьер' — всё это ранние стадии, до picked_up. ─────────
    "заказ подтвержден":            "sent_to_carrier",
    "заказ утвержден":              "sent_to_carrier",
    "заказ проверяется":            "sent_to_carrier",
    "на утверждении клиента":       "sent_to_carrier",
    "назначен курьер":              "sent_to_carrier",
    "принят. идет обработка":       "sent_to_carrier",
    "оформлен":                     "sent_to_carrier",
    "принят":                       "sent_to_carrier",
    "принято":                      "sent_to_carrier",
    "поступил":                     "sent_to_carrier",

    # ── In transit between warehouses (fallback for бесчисленных
    # «груз в транзите X→Y», «отправлен из ... в ...», «получен на склад») ─
    "в пути":                       "in_transit",
    "в транзите":                   "in_transit",
    "транзит":                      "in_transit",
    "отгружен":                     "in_transit",
    "перемещ":                      "in_transit",  # перемещён/перемещено
    "получен на склад":             "in_transit",
    "склада на другой":             "in_transit",
    "распределительного центра":    "in_transit",
    "включен в мастер-накладную":   "in_transit",
    "выбыл со склада":              "in_transit",
    "подготовлен к отправке":       "in_transit",
    "процессе транспортировки":     "in_transit",
    "отправлен":                    "in_transit",

    # Bare "прибыл" без контекста — считаем arrived. После всех
    # специфичных "прибыл ..." — те выигрывают. ────────────────────────
    "прибыл":                       "arrived",
    "прибыло":                      "arrived",
}


_UNKNOWN_STATUS = "carrier_unknown"


# ---------------------------------------------------------------------------
# GUID → internal status
# ---------------------------------------------------------------------------
# CSE docs (Tracking method) recommend keying off status GUIDs, not names:
# "используйте GUID статуса, а не его название. Название может измениться,
# GUID остаётся постоянным". This map takes precedence over the substring
# fallback below. Populate it with GUIDs verified from live CSE responses.
# Anchor entries known from the CSE integration guide:
_STATUS_GUID_MAP: dict[str, str] = {
    # Финальный статус доставки — "Доставка успешно выполнена".
    "8e5ded66-a8f5-4fa8-b863-03e1e0406df5": "delivered",
}


def _map_status(carrier_status: str, guid: str = "") -> str:
    """Resolve a CSE status to an internal Novex status.

    Priority:
      1. GUID lookup (stable across CSE renames).
      2. Substring lookup on the localised status name (legacy path — kept
         as a fallback because most GUIDs are not yet populated in the map).
      3. `carrier_unknown` — polling scheduler treats this as "do not change
         internal order.status", but the raw event is still persisted so the
         customer sees the timeline entry.

    Unknown GUIDs and unknown names are logged separately (rate-limited) so
    ops can populate `_STATUS_GUID_MAP` from prod traffic.
    """
    guid_norm = (guid or "").strip().lower()
    if guid_norm and guid_norm in _STATUS_GUID_MAP:
        return _STATUS_GUID_MAP[guid_norm]

    normalized = carrier_status.strip().lower()
    for key, mapped in _STATUS_MAP.items():
        if key in normalized:
            if guid_norm:
                # Name matched but GUID is not yet in the map — log so ops
                # can extend _STATUS_GUID_MAP with the stable identifier.
                log_once_per(
                    logger,
                    f"cse-guid-unknown:{guid_norm}",
                    "CSEPollingAdapter: status GUID %s not in _STATUS_GUID_MAP "
                    "but matched by name %r → mapped to %s",
                    guid_norm, carrier_status, mapped,
                )
            return mapped

    log_once_per(
        logger,
        f"cse-unmapped:{normalized!r}:{guid_norm}",
        "CSEPollingAdapter: unmapped carrier status guid=%s name=%r "
        "→ keeping order status unchanged",
        guid_norm or "-", carrier_status,
    )
    return _UNKNOWN_STATUS


def _parse_datetime(value: str) -> datetime:
    # Truncated to whole seconds so the polling-scheduler dedup key
    # (carrier_status, occurred_at) is comparable across adapters — Azimuth
    # emits microseconds, CSE only seconds.
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(microsecond=0)
        except ValueError:
            continue
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


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

        # client_number is our internal ClientNumber (NOVEX-XXXXXX) that CSE
        # echoes back and uses to link the outbound waybill with its return
        # (Возвратная накладная). When present, tracking() sends it as a
        # second lookup key so we see both legs in one response. The scheduler
        # stashes it into creds["client_number"] — leaving it out here keeps
        # backwards compatibility (single-leg tracking still works).
        client_number = creds.get("client_number") or None

        try:
            raw_events = client.tracking(
                tracking_number, effective_creds, client_number=client_number
            )
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
            mapped = _map_status(carrier_status, ev.get("guid", ""))
            planned_raw = ev.get("planned_delivery_at") or ""
            delivered_raw = ev.get("delivered_at") or ""
            events.append(TrackingEventData(
                status=mapped,
                carrier_status=carrier_status,
                location=ev.get("location") or None,
                occurred_at=occurred_at,
                description=ev.get("comment") or carrier_status or None,
                planned_delivery_at=_parse_datetime(planned_raw) if planned_raw else None,
                delivered_at=_parse_datetime(delivered_raw) if delivered_raw else None,
            ))

        logger.debug(
            "CSEPollingAdapter: %d events for waybill=%s", len(events), tracking_number
        )
        return events
