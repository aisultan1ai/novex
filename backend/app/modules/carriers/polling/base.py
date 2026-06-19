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


class CarrierPollingAdapter(ABC):
    carrier_code: str

    @abstractmethod
    def fetch_status(self, tracking_number: str, creds: dict) -> list[TrackingEventData]:
        """Return list of new tracking events for tracking_number.
        creds: dict built from CarrierAPICredentials (api_url + extra_config fields).
        Raise on network/auth errors."""
        ...
