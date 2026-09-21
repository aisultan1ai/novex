from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TrackingEventData:
    status: str
    carrier_status: str
    location: str | None
    occurred_at: datetime
    description: str | None = field(default=None)
    # CSE-specific: плановая дата доставки. Обновляется при документе
    # «Переадресация» и должна попадать в клиентский timeline отдельно от
    # occurred_at. Другие адаптеры (Exline, Azimuth) не эмитят её сегодня.
    planned_delivery_at: datetime | None = field(default=None)
    # Фактическое время доставки. Проставляется CSE только для финального
    # статуса «Доставка успешно выполнена».
    delivered_at: datetime | None = field(default=None)


class CarrierPollingAdapter(ABC):
    carrier_code: str

    @abstractmethod
    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        """Return list of new tracking events for tracking_number.
        creds: dict built from CarrierAPICredentials (api_url + extra_config fields).
        Raise on network/auth errors."""
        ...
