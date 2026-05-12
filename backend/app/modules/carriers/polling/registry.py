from __future__ import annotations

from app.modules.carriers.polling.base import CarrierPollingAdapter

POLLING_ADAPTERS: dict[str, CarrierPollingAdapter] = {}


def register_adapter(adapter: CarrierPollingAdapter) -> None:
    POLLING_ADAPTERS[adapter.carrier_code] = adapter


def get_adapter(carrier_code: str) -> CarrierPollingAdapter | None:
    return POLLING_ADAPTERS.get(carrier_code)
