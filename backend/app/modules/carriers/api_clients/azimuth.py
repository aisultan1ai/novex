from __future__ import annotations

import logging

import httpx

from app.modules.carriers.api_clients.base import CarrierAPIClient, InvoiceResult

logger = logging.getLogger(__name__)

_TIMEOUT = 15


class AzimuthAPIClient(CarrierAPIClient):
    carrier_code = "azimuth"

    def create_invoice(self, order_data: dict, creds: dict) -> InvoiceResult:
        api_url = creds["api_url"].rstrip("/")
        token = creds["api_token"]

        sender = order_data.get("sender", {})
        recipient = order_data.get("recipient", {})
        packages = order_data.get("packages", [])

        total_weight = sum(
            p.get("weight_kg", 0) * p.get("quantity", 1) for p in packages
        )
        total_qty = sum(p.get("quantity", 1) for p in packages)
        notes_parts = [p["description"] for p in packages if p.get("description")]

        body = {
            "sender_name": sender.get("full_name", ""),
            "sender_city": sender.get("city", ""),
            "sender_address": sender.get("address", ""),
            "sender_phone": sender.get("phone", ""),
            "receiver_name": recipient.get("full_name", ""),
            "receiver_city": recipient.get("city", ""),
            "receiver_address": recipient.get("address", ""),
            "receiver_phone": recipient.get("phone", ""),
            "service_type": int(creds.get("service_type", 2)),
            "payment_type": int(creds.get("payment_type", 2)),
            "payer": int(creds.get("payer", 1)),
            "quantity": total_qty,
            "weight": round(float(total_weight), 3),
            "declared_value": float(order_data.get("declared_value", 0)),
            "cod": None,
            "notes": "; ".join(notes_parts) if notes_parts else None,
        }

        payer_tin = creds.get("payer_tin", "")
        if payer_tin:
            body["payer_tin"] = payer_tin

        resp = httpx.post(
            f"{api_url}/api/integration/invoices",
            json=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # Azimuth may return waybill_number / invoice_number / id — handle variants
        waybill_number = (
            data.get("waybill_number")
            or data.get("invoice_number")
            or str(data.get("id", ""))
        )
        if not waybill_number:
            raise RuntimeError(f"Azimuth API did not return a waybill number. Response: {data}")

        carrier_invoice_id = str(data.get("id") or waybill_number)
        logger.info(
            "Azimuth invoice created: waybill=%s invoice_id=%s order=%s",
            waybill_number,
            carrier_invoice_id,
            order_data.get("order_id"),
        )

        # Immediately fetch the PDF
        pdf_bytes: bytes | None = None
        try:
            pdf_bytes = self.get_invoice_pdf(waybill_number, creds)
        except Exception as exc:
            logger.warning("Azimuth PDF fetch failed (non-fatal): %s", exc)

        return InvoiceResult(
            waybill_number=waybill_number,
            carrier_invoice_id=carrier_invoice_id,
            waybill_pdf_bytes=pdf_bytes,
        )

    def get_invoice_pdf(self, invoice_id: str, creds: dict) -> bytes:
        api_url = creds["api_url"].rstrip("/")
        token = creds["api_token"]
        resp = httpx.get(
            f"{api_url}/api/integration/pdf/invoices/{invoice_id}",
            params={"download": "1"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.content

    def cancel_invoice(self, invoice_id: str, creds: dict) -> bool:
        # Azimuth не предоставляет публичный API для отмены накладных.
        # Для отмены необходимо обратиться напрямую в службу поддержки Azimuth.
        logger.warning("Azimuth cancel_invoice: API not available, invoice_id=%s", invoice_id)
        raise RuntimeError(
            f"Отмена накладной {invoice_id} через API Azimuth недоступна. "
            "Обратитесь напрямую в службу поддержки Azimuth для аннулирования отправления."
        )

    def test_connection(self, creds: dict) -> bool:
        """GET /api/integration/invoices (list) as a connectivity check."""
        api_url = creds["api_url"].rstrip("/")
        token = creds["api_token"]
        resp = httpx.get(
            f"{api_url}/api/integration/invoices",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
