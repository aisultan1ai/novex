from __future__ import annotations

import logging

import httpx

from app.modules.carriers.api_clients.base import CarrierAPIClient, CarrierServiceOption, InvoiceResult

logger = logging.getLogger(__name__)

_TIMEOUT = 15


class AzimuthAPIClient(CarrierAPIClient):
    carrier_code = "azimuth"

    def create_invoice(self, order_data: dict, creds: dict) -> InvoiceResult:
        import secrets

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

        # Build service flags for notes
        service_flags: list[str] = []
        if order_data.get("fragile"):
            service_flags.append("ХРУПКИЙ ГРУЗ")
        if order_data.get("call_before_delivery"):
            service_flags.append("ПОЗВОНИТЬ ПЕРЕД ДОСТАВКОЙ")
        if order_data.get("insurance"):
            service_flags.append("СТРАХОВАНИЕ")
        if service_flags:
            notes_parts = service_flags + notes_parts

        # Azimuth waybill_number: exactly 12 chars, format from their sample
        # "123456RS7890" = 6 digits + 2 uppercase letters + 4 digits.
        import string
        digits1 = f"{secrets.randbelow(1_000_000):06d}"
        letters = "".join(secrets.choice(string.ascii_uppercase) for _ in range(2))
        digits2 = f"{secrets.randbelow(10_000):04d}"
        waybill_number = f"{digits1}{letters}{digits2}"

        body = {
            "waybill_number": waybill_number,
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
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                # Force Laravel to return the full errors map instead of the
                # abbreviated "(and N more errors)" fallback message.
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=_TIMEOUT,
        )
        # Azimuth uses HTTP 500 for validation errors — surface all field errors
        # instead of a generic 500. Try to parse `errors` map if Laravel returned it.
        if resp.status_code >= 400:
            body_preview = resp.text[:800] if resp.text else "<empty>"
            errors_summary: str
            try:
                jbody = resp.json()
                if isinstance(jbody.get("errors"), dict):
                    errors_summary = "; ".join(
                        f"{field}: {', '.join(msgs) if isinstance(msgs, list) else msgs}"
                        for field, msgs in jbody["errors"].items()
                    )
                elif isinstance(jbody.get("message"), str):
                    errors_summary = jbody["message"]
                else:
                    errors_summary = body_preview
            except Exception:
                errors_summary = body_preview
            logger.warning(
                "Azimuth create_invoice failed: status=%s FULL_BODY=%s SENT_WAYBILL=%s",
                resp.status_code, resp.text, waybill_number,
            )
            raise RuntimeError(
                f"Azimuth API вернул {resp.status_code}: {errors_summary}"
            )
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

    def get_available_services(
        self,
        creds: dict,
        from_city: str = "",
        to_city: str = "",
    ) -> list[CarrierServiceOption]:
        return [
            CarrierServiceOption(
                code="fragile",
                name="Хрупкий груз",
                available=True,
                note="Отмечается в поле примечания накладной",
            ),
            CarrierServiceOption(
                code="insurance",
                name="Страхование (объявленная ценность)",
                available=True,
                note="Тариф уточняется у перевозчика; передаётся через поле declared_value",
            ),
            CarrierServiceOption(
                code="call_before_delivery",
                name="Звонок перед доставкой",
                available=True,
                note="Включено в тариф",
            ),
        ]

    def test_connection(self, creds: dict) -> bool:
        """POST /api/integration/invoices with an empty body — Azimuth returns
        422 when auth is OK but body is invalid, and 401 when the token is bad.

        Azimuth is built on Laravel and misconfigures API auth: when the token
        is missing/invalid, Laravel tries to redirect to a `login` route that
        doesn't exist and returns HTTP 500 with body
        `{"message":"Route [login] not defined."}`. We detect that pattern and
        surface it as an auth failure.
        """
        api_url = creds["api_url"].rstrip("/")
        token = (creds.get("api_token") or "").strip()
        if not token:
            raise RuntimeError("Bearer-токен пустой. Вставьте токен в поле 'API Токен'.")

        resp = httpx.post(
            f"{api_url}/api/integration/invoices",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={},
            timeout=10,
        )
        # 422 = validation error → token is valid
        # 200/201 = accepted (shouldn't happen with empty body but just in case)
        logger.info(
            "Azimuth test_connection: status=%s body=%s",
            resp.status_code, resp.text[:300],
        )
        if resp.status_code in (200, 201, 422):
            return True
        if resp.status_code == 401:
            raise RuntimeError("Токен недействителен (401 Unauthorized)")
        if resp.status_code == 403:
            raise RuntimeError("Нет прав на API (403 Forbidden)")
        if resp.status_code == 500:
            body_lower = resp.text.lower()
            # Auth failure: Laravel redirects to `login` route which isn't defined
            if "route [login]" in body_lower or "unauthenticated" in body_lower:
                raise RuntimeError(
                    "Токен не принят Azimuth. "
                    "Свяжитесь с Azimuth за корректным Bearer-токеном для API интеграции."
                )
            # Validation errors: Azimuth uses HTTP 500 for validation failures.
            # "field is required" / "must be" / "field must be a" etc. → auth is OK
            if (
                "field is required" in body_lower
                or "field must" in body_lower
                or "must be" in body_lower
                or "and" in body_lower and "errors" in body_lower
            ):
                return True
            raise RuntimeError(
                f"Azimuth вернул 500. Ответ: {resp.text[:200]}"
            )
        raise RuntimeError(
            f"Azimuth вернул {resp.status_code}. Ответ: {resp.text[:200]}"
        )
