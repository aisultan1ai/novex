from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from app.modules.carriers.api_clients.base import CarrierAPIClient, CarrierServiceOption, InvoiceResult
from app.modules.carriers.pii_mask import mask_pii_text

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://home.courierexe.ru/api/"
# Split connect vs read: connect must be fast (fail-fast on DNS / TCP), read
# can be generous (Exline's XML PDF export can be slow). Previously the client
# used a single 30s timeout and the polling adapter a different 15s — both
# now derive from the same base value.
_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)
# Retry policy for transient network errors (connect refused, timeout, 5xx).
# Applied by _post_xml — SaveWaybillOffice / statusreq become resilient to a
# 5-second Exline blip without escalating to DispatchWorker retry.
_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = (0.5, 1.5)

# Маппинг внутреннего tariff_code → код услуги Exline (<service> в API)
_TARIFF_TO_SERVICE: dict[str, str] = {
    "standard":  "2",
    "express":   "3",
    "urgent":    "5",
    # на случай если snapshot хранит русское название
    "стандарт":  "2",
    "экспресс":  "3",
    "срочный":   "5",
}


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


class ExlineAPIClient(CarrierAPIClient):
    """
    Интеграция с MeaSoft Courier (Exline/Emu).
    Протокол: HTTP POST, тело — XML UTF-8.
    Документация: https://wiki.courierexe.ru/index.php?title=API

    Учётные данные берутся из extra_config записи CarrierAPICredentials:
        extra    — идентификатор компании (поле extra в XML)
        login    — логин
        password — пароль
    api_url  — базовый URL (по умолчанию https://home.courierexe.ru/api/)
    """

    carrier_code = "exline"

    @staticmethod
    def _post_with_retry(
        api_url: str,
        xml_body: str,
    ) -> httpx.Response:
        """POST with a small retry budget for transient failures.

        Retries on:
          * network errors (`httpx.TransportError` — connect refused, DNS,
            timeout, TLS handshake failures)
          * HTTP 5xx from Exline (their backend occasionally throws 502/504
            during deploys)

        4xx responses are NOT retried — those are permanent (bad credentials,
        malformed XML, etc.) and would just waste time.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = httpx.post(
                    api_url,
                    content=xml_body.encode("utf-8"),
                    headers={"Content-Type": "text/xml; charset=utf-8"},
                    timeout=_TIMEOUT,
                )
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt >= _MAX_RETRIES:
                    logger.warning(
                        "Exline: transport error after %d retries: %s",
                        attempt, exc,
                    )
                    raise
                delay = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                logger.info(
                    "Exline: transport error (%s), retrying in %.1fs (attempt %d/%d)",
                    exc, delay, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(delay)
                continue

            if resp.status_code >= 500 and attempt < _MAX_RETRIES:
                delay = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                logger.info(
                    "Exline: HTTP %s, retrying in %.1fs (attempt %d/%d)",
                    resp.status_code, delay, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(delay)
                continue

            resp.raise_for_status()
            return resp

        # Unreachable — the loop either returns or raises.
        raise RuntimeError(f"Exline: exhausted retries: {last_exc}")

    def _post_xml(self, xml_body: str, api_url: str) -> ET.Element:
        resp = self._post_with_retry(api_url, xml_body)
        return ET.fromstring(resp.text)

    def _post_xml_raw(self, xml_body: str, api_url: str) -> httpx.Response:
        return self._post_with_retry(api_url, xml_body)

    def _auth_tag(self, creds: dict) -> str:
        extra = creds.get("extra", "")
        login = creds.get("login", "")
        password = creds.get("password", "")
        return f'<auth extra="{_esc(extra)}" login="{_esc(login)}" pass="{_esc(password)}"/>'

    def _api_url(self, creds: dict) -> str:
        return creds.get("api_url", _DEFAULT_API_URL).rstrip("/") + "/"

    # ── public interface ────────────────────────────────────────────────────

    def create_invoice(self, order_data: dict, creds: dict) -> InvoiceResult:
        sender = order_data.get("sender", {})
        recipient = order_data.get("recipient", {})
        packages = order_data.get("packages", [])
        order_id = order_data.get("order_id", "")
        orderno = order_data.get("order_reference") or f"NOVEX-{int(order_id):06d}"

        total_weight = sum(
            p.get("weight_kg", 0) * p.get("quantity", 1) for p in packages
        )
        total_qty = sum(p.get("quantity", 1) for p in packages)
        descriptions = [p["description"] for p in packages if p.get("description")]

        service_markers: list[str] = []
        if order_data.get("fragile"):
            service_markers.append("ХРУПКИЙ")
        if order_data.get("call_before_delivery"):
            service_markers.append("ПОЗВОНИТЬ ПЕРЕД ДОСТАВКОЙ")
        if order_data.get("insurance"):
            service_markers.append("СТРАХОВАНИЕ")
        # Exline XML has no dedicated tax-id field. Stamp ИИН / БИН into the
        # enclosure so it shows up on the printed waybill, which is what KZ
        # accountants need for reconciliation.
        tax_markers: list[str] = []
        s_tax = str(sender.get("tax_id", "")).strip()
        r_tax = str(recipient.get("tax_id", "")).strip()
        if s_tax:
            tax_markers.append(f"ИИН/БИН отпр.: {s_tax}")
        if r_tax:
            tax_markers.append(f"ИИН/БИН пол.: {r_tax}")
        all_parts = service_markers + tax_markers + descriptions
        enclosure = _esc("; ".join(all_parts) if all_parts else "Посылка")

        # inshprice (Объявленная ценность) — send only when insurance is explicitly
        # requested AND we have a real declared value. Exline validates inshprice
        # against account rules; sending it for a non-insured shipment triggers
        # error 11 or silently upcharges the order.
        declared_value = float(order_data.get("declared_value") or 0)
        wants_insurance = bool(order_data.get("insurance"))
        inshprice_tag = (
            f"    <inshprice>{declared_value:.2f}</inshprice>\n"
            if wants_insurance and declared_value > 0
            else ""
        )

        tariff_raw = (order_data.get("tariff_code") or "").lower().strip()
        service_code = _TARIFF_TO_SERVICE.get(tariff_raw, "")
        service_tag = f"    <service>{service_code}</service>\n" if service_code else ""

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<neworder>
  {self._auth_tag(creds)}
  <order orderno="{_esc(orderno)}">
    <sender>
      <person>{_esc(sender.get("full_name", ""))}</person>
      <phone>{_esc(sender.get("phone", ""))}</phone>
      <town>{_esc(sender.get("city", ""))}</town>
      <address>{_esc(sender.get("address", "") or sender.get("address_line1", ""))}</address>
      <date>{date.today().isoformat()}</date>
    </sender>
    <receiver>
      <person>{_esc(recipient.get("full_name", ""))}</person>
      <company>{_esc(recipient.get("company") or recipient.get("full_name", ""))}</company>
      <phone>{_esc(recipient.get("phone", ""))}</phone>
      <town>{_esc(recipient.get("city", ""))}</town>
      <address>{_esc(recipient.get("address", "") or recipient.get("address_line1", ""))}</address>
    </receiver>
    <weight>{round(float(total_weight), 3)}</weight>
    <quantity>{int(total_qty)}</quantity>
    <paytype>NO</paytype>
{service_tag}{inshprice_tag}    <enclosure>{enclosure}</enclosure>
  </order>
</neworder>"""

        root = self._post_xml(xml, self._api_url(creds))

        found = root.find("createorder")
        node = found if found is not None else root

        error = node.attrib.get("error", "1")
        errormsg = node.attrib.get("errormsg", node.attrib.get("errormsgru", ""))
        orderno = node.attrib.get("orderno", "")
        barcode = node.attrib.get("barcode", orderno)

        if not orderno:
            # Response echoes our order XML back — sender ФИО/телефон/адрес
            # would leak to Sentry if logged raw. mask_pii_text redacts
            # <person>, <phone>, <address>, phone numbers and emails.
            raw_response = ET.tostring(root, encoding="unicode")
            raise RuntimeError(
                f"Exline error {error}: {errormsg or 'no orderno returned'}. "
                f"Response: {mask_pii_text(raw_response)}"
            )

        if error != "0":
            logger.warning("Exline returned orderno=%s with non-zero error=%s: %s", orderno, error, errormsg)

        logger.info(
            "Exline invoice created: orderno=%s barcode=%s order_id=%s",
            orderno, barcode, order_id,
        )

        pdf_bytes: bytes | None = None
        try:
            pdf_bytes = self.get_invoice_pdf(orderno, creds)
            logger.info("Exline: waybill PDF fetched for orderno=%s (%d bytes)", orderno, len(pdf_bytes))
        except Exception as exc:
            logger.warning("Exline: could not fetch waybill PDF for orderno=%s: %s", orderno, exc)

        # waybill_number stores the identifier used for statusreq/cancelorder/waybill API calls.
        # Exline statusreq <orderno> requires the client-submitted orderno (e.g. NOVEX-000001),
        # NOT the internal barcode. carrier_invoice_id holds the barcode for reference/display.
        return InvoiceResult(
            waybill_number=orderno,
            carrier_invoice_id=barcode or orderno,
            waybill_pdf_bytes=pdf_bytes,
        )

    def get_invoice_pdf(self, invoice_id: str, creds: dict) -> bytes:
        """Получить PDF накладной через официальный API метод waybill (раздел 15).

        API принимает XML с auth-тегом (те же credentials что и для создания заказа)
        и возвращает документ накладной. Авторизация — в XML, не через браузерную сессию.
        """
        import base64

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<waybill>
  {self._auth_tag(creds)}
  <orders>
    <order orderno="{_esc(invoice_id)}" />
  </orders>
  <form>1</form>
</waybill>"""

        resp = self._post_xml_raw(xml, self._api_url(creds))
        content_type = resp.headers.get("content-type", "").lower()

        # Случай 1: API вернул PDF бинарно
        if "pdf" in content_type or "octet-stream" in content_type:
            logger.info(
                "Exline waybill: PDF получен напрямую, invoice_id=%s size=%d",
                invoice_id, len(resp.content),
            )
            return resp.content

        body = resp.text.strip()

        # Случай 2: XML-ответ. По документации Exline waybill возвращает
        #   <waybill><file name="...">BASE64_PDF</file></waybill>
        # В XML также может быть атрибут error != "0".
        if body.startswith("<"):
            try:
                root = ET.fromstring(body)
            except ET.ParseError:
                root = None
            if root is not None:
                err = root.attrib.get("error", "0")
                if err and err != "0":
                    msg = (
                        root.attrib.get("errormsgru")
                        or root.attrib.get("errormsg", "unknown")
                    )
                    raise RuntimeError(f"Exline waybill API error {err}: {msg}")
                # Реальный API возвращает <waybill><content>BASE64</content></waybill>.
                # Вики упоминает <file> — на всякий случай поддерживаем оба.
                # NB: Element.__bool__ ложен у элемента без детей, поэтому
                # используем явный is-not-None каскад вместо `a or b`.
                file_node = root.find(".//content")
                if file_node is None:
                    file_node = root.find(".//file")
                if file_node is not None and file_node.text:
                    raw_b64 = "".join(file_node.text.split())
                    try:
                        decoded = base64.b64decode(raw_b64, validate=True)
                    except Exception as exc:
                        raise RuntimeError(
                            f"Exline waybill: не удалось декодировать base64 в <file> "
                            f"для invoice_id={invoice_id}: {exc}"
                        ) from exc
                    if decoded[:4] != b"%PDF":
                        raise RuntimeError(
                            f"Exline waybill: декодированный <file> не PDF "
                            f"для invoice_id={invoice_id} (первые байты: {decoded[:8]!r})"
                        )
                    logger.info(
                        "Exline waybill: PDF извлечён из <file>, invoice_id=%s size=%d",
                        invoice_id, len(decoded),
                    )
                    return decoded

        # Случай 3: API вернул PDF как "голую" base64-строку (без XML-обёртки).
        raw_b64 = body.replace("\n", "").replace("\r", "").replace(" ", "")
        try:
            decoded = base64.b64decode(raw_b64, validate=True)
            if decoded[:4] == b"%PDF":
                logger.info(
                    "Exline waybill: PDF декодирован из base64, invoice_id=%s size=%d",
                    invoice_id, len(decoded),
                )
                return decoded
        except Exception:
            pass

        # Случай 4: HTML-документ накладной — конвертируем в PDF через weasyprint
        try:
            import weasyprint
        except ImportError as exc:
            raise RuntimeError("weasyprint не установлен: pip install weasyprint") from exc

        if not body:
            raise RuntimeError(f"Exline waybill API вернул пустой ответ для invoice_id={invoice_id}")

        pdf_bytes: bytes = weasyprint.HTML(
            string=body,
            base_url=self._api_url(creds),
        ).write_pdf()

        logger.info(
            "Exline waybill: HTML→PDF сконвертирован, invoice_id=%s size=%d bytes",
            invoice_id, len(pdf_bytes),
        )
        return pdf_bytes

    def cancel_invoice(self, invoice_id: str, creds: dict) -> bool:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<cancelorder>
  {self._auth_tag(creds)}
  <order orderno="{_esc(invoice_id)}" />
</cancelorder>"""
        try:
            root = self._post_xml(xml, self._api_url(creds))
            order_node = root.find("order")
            if order_node is None:
                logger.warning(
                    "Exline cancel_invoice: no <order> in response for orderno=%s: %s",
                    invoice_id,
                    mask_pii_text(ET.tostring(root, encoding="unicode")),
                )
                return False
            err = order_node.attrib.get("error", "1")
            if err != "0":
                # Full raw XML for debugging — Exline sometimes puts a hint in
                # attributes we don't parse (errormsg vs errormsgru, extra
                # fields, etc.). PII-masked for safety.
                raw = mask_pii_text(ET.tostring(root, encoding="unicode"))
                logger.warning(
                    "Exline cancel_invoice failed: orderno=%s error=%s "
                    "msgru=%s msg=%s attribs=%s raw=%s",
                    invoice_id,
                    err,
                    order_node.attrib.get("errormsgru", ""),
                    order_node.attrib.get("errormsg", ""),
                    dict(order_node.attrib),
                    raw,
                )
                return False
            return True
        except Exception as exc:
            logger.warning("Exline cancel_invoice exception: %s", exc)
            return False

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
                note="Отмечается в поле вложения (enclosure)",
            ),
            CarrierServiceOption(
                code="insurance",
                name="Страхование (объявленная ценность)",
                available=True,
                note="Поле inshprice; тариф зависит от объявленной ценности",
            ),
            CarrierServiceOption(
                code="call_before_delivery",
                name="Звонок перед доставкой",
                available=True,
                note="Включено в тариф",
            ),
        ]

    def get_city_list(self, creds: dict) -> list[dict]:
        """Справочник городов Exline (раздел 16 API)."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<townlist>"
            f"{self._auth_tag(creds)}"
            "</townlist>"
        )
        root = self._post_xml(xml, self._api_url(creds))
        cities = []
        def _town_val(t: ET.Element, k: str) -> str:
            child = t.find(k)
            return t.attrib.get(k) or (child.text if child is not None else "") or ""

        for town in root.findall("town"):
            cities.append({k: _town_val(town, k) for k in ("name", "code", "region", "district", "type")})
        return cities

    def test_connection(self, creds: dict) -> bool:
        # statusreq with a same-day range is the cheapest auth probe: it hits the
        # authenticated endpoint but does not require an existing order. Exline
        # replies with error="1" for bad credentials, error="0" otherwise.
        today = date.today().isoformat()
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<statusreq>
  {self._auth_tag(creds)}
  <datefrom>{today}</datefrom>
  <dateto>{today}</dateto>
</statusreq>"""
        root = self._post_xml(xml, self._api_url(creds))
        error = root.attrib.get("error", "0")
        if error == "1":
            errmsg = root.attrib.get("errormsg") or root.attrib.get("errormsgru") or "authorization error"
            raise RuntimeError(f"Exline: {errmsg}")
        return True
