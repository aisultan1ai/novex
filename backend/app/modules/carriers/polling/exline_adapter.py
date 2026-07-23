from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

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
    Учётные данные передаются из CarrierAPICredentials.extra_config:
        extra    — идентификатор компании
        login    — логин
        password — пароль
    api_url берётся из CarrierAPICredentials.api_url.
    Если creds пустой — fallback на env vars (для dev-окружения).
    """

    carrier_code = "exline"

    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        extra = str(creds.get("extra") or os.getenv("EXLINE_EXTRA") or "")
        login = str(creds.get("login") or os.getenv("EXLINE_LOGIN") or "")
        password = str(creds.get("password") or os.getenv("EXLINE_PASSWORD") or "")
        api_url = str(creds.get("api_url") or os.getenv("EXLINE_API_URL") or _DEFAULT_API_URL).rstrip("/") + "/"

        if not extra or not login:
            logger.warning(
                "ExlineAdapter: no credentials available for tracking (orderno=%s)",
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
