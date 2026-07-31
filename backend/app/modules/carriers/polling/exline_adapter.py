from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx

from app.common.log_ratelimit import log_once_per
from app.core.config import get_settings
from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://home.courierexe.ru/api/"
# Same shape as the main client — splitting connect/read so a slow response
# on one shipment cannot block the entire polling tick.
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)

# Маппинг статусов Exline (MeaSoft Courier XML API) → внутренние статусы
# Novex. Полный enum задокументирован в
# https://wiki.courierexe.ru/index.php?title=API (31 значение). Раньше у нас
# было только 6 ключей, а всё неизвестное силент-fallback'ом уходило в
# in_transit — что скрывало реальные проблемы (LOST → «В пути» у клиента,
# UNCONFIRM → «В пути» вместо «Попытка не удалась» и т.п.).
#
# Semantic corrections vs старого маппинга:
#   ACCEPTED  picked_up → in_transit  (это «получен складом», не забор)
#   DELIVERY  in_transit → out_for_delivery  (это «выдан курьеру»)
#   RETURN    удалён — такого кода нет в docs, был легаси
_STATUS_MAP: dict[str, str] = {
    # ── Начальные ──────────────────────────────────────────────────────
    "NEW":             "sent_to_carrier",   # успешно создан, передан в КС
    "NEWPICKUP":       "sent_to_carrier",   # создан забор
    "AWAITING_SYNC":   "sent_to_carrier",   # ожидает синхронизации

    # ── Забор / склад ─────────────────────────────────────────────────
    "PICKUP":          "picked_up",         # забран у отправителя
    "ACCEPTED":        "in_transit",        # получен складом (НЕ забор)
    "STORETAKE":       "in_transit",
    "PICKUPTRANS":     "in_transit",
    "WMSASSEMBLED":    "in_transit",
    "WMSDISASSEMBLED": "in_transit",
    "INVENTORY":       "in_transit",

    # ── Перемещение между складами ────────────────────────────────────
    "DEPARTURING":     "in_transit",
    "DEPARTURE":       "in_transit",
    "TRANSACCEPTED":   "in_transit",
    "DEPARTUREDELAY":  "in_transit",

    # ── Таможня ───────────────────────────────────────────────────────
    "CUSTOMSPROCESS":  "customs_hold",
    "CUSTOMSDELAY":    "customs_hold",
    "CUSTOMSFINISHED": "in_transit",

    # ── Согласование / подготовка ─────────────────────────────────────
    "CONFIRM":         "in_transit",
    "DATECHANGE":      "in_transit",
    "UNCONFIRM":       "delivery_failed",   # не удалось согласовать
    "PICKUPREADY":     "arrived",           # готов к выдаче в ПВЗ

    # ── Доставка ──────────────────────────────────────────────────────
    "DELIVERY":         "out_for_delivery", # выдан курьеру (НЕ in_transit)
    "COURIERDELIVERED": "out_for_delivery",
    "COMPLETE":         "delivered",
    "PARTIALLY":        "delivered",
    "COURIERPARTIALLY": "delivered",

    # ── Проблемы ──────────────────────────────────────────────────────
    "COURIERCANCELED": "delivery_failed",
    "LOST":            "delivery_failed",

    # ── Возврат ───────────────────────────────────────────────────────
    "COURIERRETURN":               "return_in_progress",
    "WITHDRAWN_FROM_PICKUP_POINT": "return_in_progress",
    "RETURNING":                   "return_in_progress",
    "PARTLYRETURNING":             "return_in_progress",
    "CANCELED":                    "cancelled",
    "RETURNED":                    "returned",
    "PARTLYRETURNED":              "returned",
}


def _map_status(carrier_status: str) -> str:
    """Exline → Novex status. Unknown → carrier_unknown (safe: not in state
    machine, so can_transition returns False and order status stays put).

    Раньше здесь был silent fallback на in_transit — тот же баг, от которого
    ушли в CSE. Rate-limited log помогает поймать новый код и добавить в
    _STATUS_MAP без флуда в проде.
    """
    mapped = _STATUS_MAP.get(carrier_status)
    if mapped:
        return mapped
    log_once_per(
        logger,
        f"exline-unmapped:{carrier_status!r}",
        "ExlineAdapter: unmapped carrier status %r → keeping order status unchanged",
        carrier_status,
    )
    return "carrier_unknown"


class ExlineAdapter(CarrierPollingAdapter):
    """
    Адаптер трекинга для Exline (MeaSoft Courier).
    Учётные данные передаются из CarrierAPICredentials.extra_config:
        extra    — идентификатор компании
        login    — логин
        password — пароль
    api_url берётся из CarrierAPICredentials.api_url.
    Если creds пустой — fallback на env vars (для dev-окружения).
    """

    carrier_code = "exline"

    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        # Env-var fallback is a dev-only convenience. In production every
        # carrier MUST have its credentials in CarrierAPICredentials so we
        # never accidentally poll live carriers with stale env values (which
        # would also be shared across every carrier — a footgun waiting to
        # happen). Fail fast in prod if creds are missing.
        allow_env_fallback = get_settings().environment != "production"
        extra = str(creds.get("extra") or "").strip()
        login = str(creds.get("login") or "").strip()
        password = str(creds.get("password") or "")
        api_url_raw = str(creds.get("api_url") or "").strip()
        if allow_env_fallback:
            extra = extra or (os.getenv("EXLINE_EXTRA") or "")
            login = login or (os.getenv("EXLINE_LOGIN") or "")
            password = password or (os.getenv("EXLINE_PASSWORD") or "")
            api_url_raw = api_url_raw or (os.getenv("EXLINE_API_URL") or _DEFAULT_API_URL)
        api_url = (api_url_raw or _DEFAULT_API_URL).rstrip("/") + "/"

        if not extra or not login:
            logger.warning(
                "ExlineAdapter: no credentials available for tracking (orderno=%s) "
                "— configure CarrierAPICredentials for 'exline' via admin.",
                tracking_number,
            )
            return []

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<statusreq>"
            f'<auth extra="{_esc(extra)}" login="{_esc(login)}" pass="{_esc(password)}"/>'
            f"<orderno>{_esc(tracking_number)}</orderno>"
            "</statusreq>"
        )

        try:
            resp = httpx.post(
                api_url,
                content=xml.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except Exception as exc:
            logger.warning(
                "ExlineAdapter: statusreq завершился с ошибкой (orderno=%s): %s",
                tracking_number, exc,
            )
            raise

        error = root.attrib.get("error")
        if error == "1":
            raise RuntimeError(f"Exline auth error while polling {tracking_number}")

        events: list[TrackingEventData] = []
        for order_el in root.findall("order"):
            for hist_el in order_el.findall(".//statushistory/status"):
                carrier_status = (hist_el.text or "").strip().upper()
                event_time_str = hist_el.attrib.get("eventtime", "")
                location = hist_el.attrib.get("eventstore") or None
                title = hist_el.attrib.get("title", carrier_status)

                try:
                    occurred_at = datetime.fromisoformat(event_time_str)
                except (ValueError, TypeError):
                    occurred_at = datetime.now(UTC).replace(tzinfo=None)
                # Whole-second truncation so scheduler dedup key aligns with
                # the other adapters (Azimuth µs vs CSE s vs Exline mix).
                occurred_at = occurred_at.replace(microsecond=0)
                if occurred_at.tzinfo is not None:
                    occurred_at = occurred_at.astimezone(UTC).replace(tzinfo=None)

                mapped = _map_status(carrier_status)
                events.append(TrackingEventData(
                    status=mapped,
                    carrier_status=carrier_status,
                    location=location,
                    occurred_at=occurred_at,
                    description=title,
                ))

        logger.debug(
            "ExlineAdapter: %d событий для orderno=%s", len(events), tracking_number
        )
        return events
