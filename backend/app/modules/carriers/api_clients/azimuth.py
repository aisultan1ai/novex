from __future__ import annotations

import logging

import httpx

from app.modules.carriers.api_clients.base import CarrierAPIClient, CarrierServiceOption, InvoiceResult
from app.modules.carriers.pii_mask import mask_pii_text

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

        # Azimuth waybill_number regex: ^\d*RS\d*$ + size:12
        # Must contain exactly one "RS", rest digits, total 12 chars.
        # Derived from our own order.id so it is deterministic + globally
        # unique (order.id is autoincrement, we hold the row). Previously we
        # used secrets.randbelow(10**10), which had a small but non-zero
        # birthday-collision probability; on collision Azimuth returned 500
        # and dispatch retried, potentially producing a second waybill (they
        # have no cancel). Format: 10 digits derived from order.id (zero-
        # padded, wrapped modulo 10**10 for safety with very large ids) + "RS".
        order_id = int(order_data.get("order_id") or 0)
        if order_id <= 0:
            raise RuntimeError(
                "Azimuth create_invoice: order_data['order_id'] is required "
                "to derive a collision-safe waybill_number."
            )
        digits = f"{order_id % 10**10:010d}"
        waybill_number = f"{digits}RS"

        # Azimuth caps quantity at 4 per invoice. Silently clamping would
        # mean the customer pays for N packages but the carrier receives an
        # invoice for min(N, 4) — fail loudly so admin can split the order
        # (or the customer is told to break it apart at the shipment form).
        if total_qty < 1:
            raise RuntimeError(
                "Azimuth create_invoice: количество мест должно быть не меньше 1."
            )
        if total_qty > 4:
            raise RuntimeError(
                f"Azimuth не принимает больше 4 мест в одной накладной "
                f"(получено {total_qty}). Разбейте заказ на несколько накладных."
            )
        clamped_qty = total_qty
        # declared_value must be an integer (tenge), not decimal.
        declared_value_tenge = int(round(float(order_data.get("declared_value", 0) or 0)))

        # Map platform tariff → Azimuth service_type. Azimuth values:
        # 1=Стандарт, 2=Экспресс, 3=Экспресс-пакет.
        # Priority: order's tariff_name > shipment_type > creds default.
        tariff_name_lower = (order_data.get("tariff_name") or "").lower()
        shipment_type_lower = (order_data.get("shipment_type") or "").lower()
        service_type_from_tariff: int | None = None
        if "экспресс-пакет" in tariff_name_lower or "express-package" in tariff_name_lower:
            service_type_from_tariff = 3
        elif "экспресс" in tariff_name_lower or "express" in tariff_name_lower:
            service_type_from_tariff = 2
        elif "стандарт" in tariff_name_lower or "standard" in tariff_name_lower:
            service_type_from_tariff = 1
        elif "эконом" in tariff_name_lower or "economy" in tariff_name_lower:
            # Azimuth has no "economy" — fall back to Стандарт (cheapest available).
            service_type_from_tariff = 1
        elif shipment_type_lower == "document":
            # Documents typically go via Экспресс-пакет at Azimuth.
            service_type_from_tariff = 3
        service_type = service_type_from_tariff or int(creds.get("service_type", 2))

        body = {
            "waybill_number": waybill_number,
            "sender_name": sender.get("full_name", "")[:255],
            "sender_city": sender.get("city", "")[:255],
            "sender_address": sender.get("address", "")[:255],
            "sender_phone": sender.get("phone", "")[:20],
            "receiver_name": recipient.get("full_name", "")[:255],
            "receiver_city": recipient.get("city", "")[:255],
            "receiver_address": recipient.get("address", "")[:255],
            "receiver_phone": recipient.get("phone", "")[:20],
            "service_type": service_type,
            "payment_type": int(creds.get("payment_type", 2)),
            "payer": int(creds.get("payer", 1)),
            "quantity": clamped_qty,
            "weight": round(float(total_weight), 3),
            "declared_value": declared_value_tenge,
            "cod": None,
            "notes": ("; ".join(notes_parts) if notes_parts else None) or None,
        }
        if body["notes"]:
            body["notes"] = body["notes"][:255]

        # payer_tin (Azimuth spec — exactly 12 digits) — the shipper's own
        # tax id. Take it from the sender party of the order (populated from
        # the customer profile). The admin-level `creds["payer_tin"]` is kept
        # only as a last-resort fallback for legacy orders where the sender
        # party pre-dates the tax_id field.
        sender_tax_id = str(sender.get("tax_id", "")).strip()
        payer_tin = sender_tax_id or str(creds.get("payer_tin", "")).strip()
        if not payer_tin or not payer_tin.isdigit() or len(payer_tin) != 12:
            raise RuntimeError(
                "Не указан ИИН / БИН отправителя (12 цифр). "
                "Проверьте профиль клиента или карточку отправителя в заказе."
            )
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
            body_preview = mask_pii_text(resp.text)[:800] if resp.text else "<empty>"
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
            # Response body echoes our sender/receiver JSON. Scrub before log
            # so PII does not leak to Sentry.
            logger.warning(
                "Azimuth create_invoice failed: status=%s BODY=%s SENT_WAYBILL=%s",
                resp.status_code, mask_pii_text(resp.text), waybill_number,
            )
            raise RuntimeError(
                f"Azimuth API вернул {resp.status_code}: {mask_pii_text(errors_summary)}"
            )
        data = resp.json()

        # Azimuth wraps the invoice in a `data` object and returns:
        # - `id`: their internal numeric invoice id (e.g. 73228)
        # - `bill`: the waybill number we sent back to us (e.g. "4376006623RS")
        # Older variants used `waybill_number` / `invoice_number` at the top level.
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        waybill_number = (
            inner.get("bill")
            or inner.get("waybill_number")
            or inner.get("invoice_number")
            or str(inner.get("id", ""))
        )
        if not waybill_number:
            raise RuntimeError(f"Azimuth API did not return a waybill number. Response: {data}")

        carrier_invoice_id = str(inner.get("id") or waybill_number)
        logger.info(
            "Azimuth invoice created: waybill=%s invoice_id=%s order=%s",
            waybill_number,
            carrier_invoice_id,
            order_data.get("order_id"),
        )

        # Immediately fetch the PDF — use the numeric invoice id (Azimuth's
        # route-model-binding uses id by default, not the bill/waybill string).
        pdf_bytes: bytes | None = None
        try:
            pdf_bytes = self.get_invoice_pdf(carrier_invoice_id, creds)
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

    # ── Regions search (GET /api/integration/regions/{type}) ───────────────
    # Docs (Azimuth):
    #   GET https://api.azimuthcargo.kz/api/integration/regions/{type}
    #     type   = "origin" | "destination"
    #     title  = substring of the region name (required, max 255)
    #     Auth   = Bearer <api_token>
    # Response shape is not fully documented here — call this in dev to inspect
    # what Azimuth actually returns (data[]/id/title/full_title/etc.) before
    # persisting a schema on our side.
    def search_regions(
        self,
        type_: str,
        title: str,
        creds: dict,
    ) -> dict:
        """Return the raw parsed JSON body from Azimuth's /regions endpoint.

        Read-only: this endpoint does not create anything on Azimuth's side —
        safe to call from a probe script or a manual admin trigger. Callers
        get back the raw dict/list so we can inspect the response shape.
        """
        if type_ not in ("origin", "destination"):
            raise ValueError(f"Azimuth regions type must be 'origin' or 'destination', got '{type_}'")
        title = (title or "").strip()
        if not title:
            raise ValueError("Azimuth regions search: title is required (Laravel validation)")

        api_url = creds["api_url"].rstrip("/")
        token = creds["api_token"]

        resp = httpx.get(
            f"{api_url}/api/integration/regions/{type_}",
            params={"title": title},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code >= 400:
            body_preview = (resp.text or "")[:800]
            logger.warning(
                "Azimuth regions search failed: type=%s title=%r status=%s body=%s",
                type_, title, resp.status_code, body_preview,
            )
            raise RuntimeError(
                f"Azimuth /regions/{type_} вернул {resp.status_code}: {body_preview}"
            )
        try:
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"Azimuth /regions/{type_} вернул невалидный JSON: {resp.text[:400]}"
            ) from exc
        logger.info(
            "Azimuth regions probe: type=%s title=%r → %d bytes",
            type_, title, len(resp.text),
        )
        return data

    # ── Order courier (POST /api/integration/order-courier) ────────────────
    # Docs (Azimuth):
    #   POST /api/integration/order-courier
    #   Required fields: sender_{name,region,address,phone}, payer_{name,region,
    #     address,phone}, service_type (1|2|3), payer_type (1|2|3), quantity
    #     (1..4), contact_person, contact_person_phone, payment (1|2).
    #   Optional: sender_tin/payer_tin (12 digits), pickup_date/pickup_time,
    #     notes.
    #
    # PROD-only endpoint: creating a pickup here dispatches a real courier.
    # Callers MUST have already validated the order (paid, invoice created)
    # and MUST be idempotent — Azimuth does not return an id we can dedup on,
    # so persist pickup_scheduled_azimuth_id on our side after a successful
    # call and refuse to re-invoke for that order.
    def schedule_pickup(self, order_data: dict, creds: dict) -> dict:
        """Send a courier pickup request to Azimuth. Returns the parsed body.

        order_data keys:
            sender_region, payer_region — exact Azimuth region titles (from
                                          azimuth_regions.title, augmented with
                                          path per Azimuth docs example)
            sender/payer name/address/phone/tin
            service_type: 1|2|3       — matched to the paid tariff
            payer_type:   1|2|3       — from creds default
            quantity:     1..4        — total packages
            pickup_date:  YYYY-MM-DD
            pickup_time:  "14:00-18:00"  (a slot label)
            contact_person, contact_person_phone
            payment:      1|2         — from creds default
            notes:        optional string
        """
        api_url = creds["api_url"].rstrip("/")
        token = creds["api_token"]

        # Build body strictly to Azimuth's validation rules — anything not in
        # this whitelist is dropped so we do not accidentally send a stray
        # field that Laravel would 422 on.
        body: dict = {
            "sender_name": str(order_data.get("sender_name", ""))[:255],
            "sender_region": str(order_data.get("sender_region", ""))[:255],
            "sender_address": str(order_data.get("sender_address", ""))[:255],
            "sender_phone": str(order_data.get("sender_phone", ""))[:20],
            "payer_name": str(order_data.get("payer_name", ""))[:255],
            "payer_region": str(order_data.get("payer_region", ""))[:255],
            "payer_address": str(order_data.get("payer_address", ""))[:255],
            "payer_phone": str(order_data.get("payer_phone", ""))[:20],
            "service_type": int(order_data.get("service_type", 2)),
            "payer_type": int(order_data.get("payer_type", 1)),
            "quantity": int(order_data.get("quantity", 1)),
            "contact_person": str(order_data.get("contact_person", ""))[:255],
            "contact_person_phone": str(order_data.get("contact_person_phone", ""))[:20],
            "payment": int(order_data.get("payment", 2)),
        }

        # Optional fields: only add when populated so we do not send explicit
        # nulls that Laravel might treat differently from omission.
        sender_tin = str(order_data.get("sender_tin") or "").strip()
        if sender_tin:
            if not sender_tin.isdigit() or len(sender_tin) != 12:
                raise RuntimeError(
                    f"Azimuth order-courier: sender_tin должен быть ровно 12 цифр "
                    f"(получено: {sender_tin!r})."
                )
            body["sender_tin"] = sender_tin
        payer_tin = str(order_data.get("payer_tin") or "").strip()
        if payer_tin:
            if not payer_tin.isdigit() or len(payer_tin) != 12:
                raise RuntimeError(
                    f"Azimuth order-courier: payer_tin должен быть ровно 12 цифр "
                    f"(получено: {payer_tin!r})."
                )
            body["payer_tin"] = payer_tin

        pickup_date = str(order_data.get("pickup_date") or "").strip()
        pickup_time = str(order_data.get("pickup_time") or "").strip()
        # Laravel rule: pickup_date required_with:pickup_time → sending time
        # without date is a hard 422.
        if pickup_time and not pickup_date:
            raise RuntimeError(
                "Azimuth order-courier: pickup_time указан, а pickup_date пустой."
            )
        if pickup_date:
            body["pickup_date"] = pickup_date
        if pickup_time:
            body["pickup_time"] = pickup_time[:50]

        notes = str(order_data.get("notes") or "").strip()
        if notes:
            body["notes"] = notes[:1000]

        # Validation rules from docs — surface early instead of getting an
        # opaque 500 from Azimuth (their Laravel returns 500 on validation).
        if body["quantity"] < 1 or body["quantity"] > 4:
            raise RuntimeError(
                f"Azimuth order-courier: quantity must be between 1 and 4 "
                f"(got {body['quantity']}). Split the shipment across multiple pickups."
            )
        if body["service_type"] not in (1, 2, 3):
            raise RuntimeError(
                f"Azimuth order-courier: service_type must be 1|2|3 (got {body['service_type']})."
            )
        if body["payer_type"] not in (1, 2, 3):
            raise RuntimeError(
                f"Azimuth order-courier: payer_type must be 1|2|3 (got {body['payer_type']})."
            )
        if body["payment"] not in (1, 2):
            raise RuntimeError(
                f"Azimuth order-courier: payment must be 1|2 (got {body['payment']})."
            )

        resp = httpx.post(
            f"{api_url}/api/integration/order-courier",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code >= 400:
            # Reuse the same Laravel-error parsing shape as create_invoice.
            body_preview = mask_pii_text(resp.text or "")[:800]
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
                "Azimuth order-courier failed: status=%s body=%s",
                resp.status_code, mask_pii_text(resp.text or ""),
            )
            raise RuntimeError(
                f"Azimuth order-courier вернул {resp.status_code}: {mask_pii_text(errors_summary)}"
            )

        try:
            data = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"Azimuth order-courier: невалидный JSON в ответе: {resp.text[:400]}"
            ) from exc
        logger.info(
            "Azimuth pickup scheduled: pickup_date=%s time=%s → status=%s",
            body.get("pickup_date"), body.get("pickup_time"), resp.status_code,
        )
        return data

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
