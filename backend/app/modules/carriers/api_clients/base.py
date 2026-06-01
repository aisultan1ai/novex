from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class InvoiceResult:
    """Результат создания накладной через API перевозчика."""
    waybill_number: str          # трекинг-номер / номер накладной
    carrier_invoice_id: str | None = None   # внутренний ID на стороне перевозчика
    waybill_pdf_bytes: bytes | None = None  # PDF накладной, если доступен сразу


class CarrierAPIClient(ABC):
    """Базовый интерфейс для всех API-интеграций перевозчиков."""

    carrier_code: str

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
