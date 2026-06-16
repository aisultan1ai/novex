from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://home.courierexe.ru/api/"
_TIMEOUT = 15

# Маппинг статусов Exline → внутренние статусы Novex
_STATUS_MAP: dict[str, str] = {
    "NEW":      "sent_to_carrier",
    "ACCEPTED": "picked_up",
    "DELIVERY": "in_transit",
    "COMPLETE": "delivered",
    "CANCELED": "cancelled",
    "RETURN":   "return_in_progress",
}


class ExlineAdapter(CarrierPollingAdapter):
    """
    Адаптер трекинга для Exline (MeaSoft Courier).
    Учётные данные читаются из переменных окружения:
        EXLINE_EXTRA     — идентификатор компании
        EXLINE_LOGIN     — логин
        EXLINE_PASSWORD  — пароль
        EXLINE_API_URL   — (опционально) кастомный URL
    """

    carrier_code = "exline"

    def __init__(self) -> None:
        self._extra = os.getenv("EXLINE_EXTRA", "")
        self._login = os.getenv("EXLINE_LOGIN", "")
        self._password = os.getenv("EXLINE_PASSWORD", "")
        self._api_url = os.getenv("EXLINE_API_URL", _DEFAULT_API_URL).rstrip("/") + "/"

    def fetch_status(self, tracking_number: str) -> list[TrackingEventData]:
        if not self._extra or not self._login:
            logger.warning(
                "ExlineAdapter: EXLINE_EXTRA / EXLINE_LOGIN не заданы — трекинг пропущен"
            )
            return []

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<statusreq>"
            f'<auth extra="{_esc(self._extra)}" login="{_esc(self._login)}" pass="{_esc(self._password)}"/>'
            f"<orderno>{_esc(tracking_number)}</orderno>"
            "</statusreq>"
        )

        try:
            resp = httpx.post(
                self._api_url,
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
                    occurred_at = datetime.utcnow()

                mapped = _STATUS_MAP.get(carrier_status, "in_transit")
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
