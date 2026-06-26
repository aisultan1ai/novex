from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class InvoiceResult:
    """Результат создания накладной через API перевозчика."""
    waybill_number: str          # трекинг-номер / номер накладной
    carrier_invoice_id: str | None = None   # внутренний ID на стороне перевозчика
    waybill_pdf_bytes: bytes | None = None  # PDF накладной, если доступен сразу


@dataclass
class CarrierServiceOption:
    """Дополнительная услуга перевозчика — результат запроса к API."""
    code: str               # внутренний код: "cod", "card_payment", "insurance", "fragile", "call_before_delivery"
    name: str               # название для отображения
    available: bool         # доступна ли услуга (для данного маршрута)
    price: Decimal | None = None    # доп. стоимость; None = включено в тариф / неизвестно
    currency: str = "KZT"
    note: str = ""          # пояснение: "2% от объявленной ценности", "при наличии кассы" и т.д.


class CarrierAPIClient(ABC):
    """Базовый интерфейс для всех API-интеграций перевозчиков."""

    carrier_code: str

    def get_available_services(
        self,
        creds: dict,
        from_city: str = "",
        to_city: str = "",
    ) -> list[CarrierServiceOption]:
        """Return additional services available for this carrier (optionally route-specific).

        Default returns an empty list. Subclasses override to provide real data.
        """
        return []

    @abstractmethod
    def create_invoice(self, order_data: dict, creds: dict) -> InvoiceResult:
        """Создать накладную через API перевозчика.

        order_data: нормализованные данные заказа (sender, recipient, packages, ...)
        creds: { api_url, api_token, **extra_config }
        """
        ...

    @abstractmethod
    def get_invoice_pdf(self, invoice_id: str, creds: dict) -> bytes:
        """Скачать PDF накладной по ID или номеру накладной."""
        ...

    @abstractmethod
    def cancel_invoice(self, invoice_id: str, creds: dict) -> bool:
        """Отменить накладную. Возвращает True при успехе."""
        ...

    @abstractmethod
    def test_connection(self, creds: dict) -> bool:
        """Проверить корректность учётных данных. Raises on error."""
        ...
