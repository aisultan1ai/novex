from __future__ import annotations

from app.modules.carriers.api_clients.azimuth import AzimuthAPIClient
from app.modules.carriers.api_clients.base import CarrierAPIClient

_REGISTRY: dict[str, CarrierAPIClient] = {
    "azimuth": AzimuthAPIClient(),
}


def get_client(carrier_code: str) -> CarrierAPIClient | None:
    """Return the API client for a carrier code, or None if not supported."""
    return _REGISTRY.get(carrier_code.lower())


def list_supported_codes() -> list[str]:
    return list(_REGISTRY.keys())
