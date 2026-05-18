from __future__ import annotations

from app.modules.carriers.polling.base import CarrierPollingAdapter, TrackingEventData


class AzimuthAdapter(CarrierPollingAdapter):
    carrier_code = "azimuth"

    def fetch_status(self, tracking_number: str) -> list[TrackingEventData]:
        # TODO: реализовать когда будет доступ к API или сайту Azimuth
        # Вариант A (API): GET https://api.azimuth.kz/tracking/{tracking_number}
        # Вариант B (HTML): GET https://azimuth.kz/tracking/{tracking_number} + BeautifulSoup  # noqa: E501
        raise NotImplementedError("AzimuthAdapter not implemented yet")
