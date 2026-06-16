from __future__ import annotations

from app.modules.carriers.polling.azimuth_adapter import AzimuthAdapter
from app.modules.carriers.polling.base import CarrierPollingAdapter
from app.modules.carriers.polling.exline_adapter import ExlineAdapter

POLLING_ADAPTERS: dict[str, CarrierPollingAdapter] = {}


def register_adapter(adapter: CarrierPollingAdapter) -> None:
    POLLING_ADAPTERS[adapter.carrier_code] = adapter


def get_adapter(carrier_code: str) -> CarrierPollingAdapter | None:
    return POLLING_ADAPTERS.get(carrier_code)


# Register all available adapters at import time
register_adapter(AzimuthAdapter())
register_adapter(ExlineAdapter())
