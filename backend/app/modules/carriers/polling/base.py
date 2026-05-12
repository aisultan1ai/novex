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
    def fetch_status(self, tracking_number: str) -> list[TrackingEventData]:
        """Return list of new tracking events. Raise on error."""
        ...
