from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from app.modules.carriers.api_clients.base import CarrierAPIClient, CarrierServiceOption, InvoiceResult

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://home.courierexe.ru/api/"
_TIMEOUT = 30


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

    def _post_xml(self, xml_body: str, api_url: str) -> ET.Element:
        resp = httpx.post(
            api_url,
            content=xml_body.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return ET.fromstring(resp.text)

    def _auth_tag(self, creds: dict) -> str:
        extra = creds.get("extra", "")
        login = creds.get("login", "")
        password = creds.get("password", "")
        return f'<auth extra="{_esc(extra)}" login="{_esc(login)}" pass="{_esc(password)}"/>'

    def _api_url(self, creds: dict) -> str:
        return creds.get("api_url", _DEFAULT_API_URL).rstrip("/") + "/"

    def _print_base_url(self, creds: dict) -> str:
        """Возвращает корневой URL инсталляции MeaSoft (без /api/).
        https://home.courierexe.ru/api/ → https://home.courierexe.ru/
        """
        api_url = self._api_url(creds)
        idx = api_url.find("/api")
        return api_url[:idx] + "/" if idx != -1 else api_url

    def _get_print_url(self, invoice_id: str, creds: dict) -> str:
        """Внутренний URL страницы печати MeaSoft. Содержит credentials — не возвращать клиентам."""
        base = self._print_base_url(creds)
        params = urllib.parse.urlencode({
            "extra": creds.get("extra", ""),
            "login": creds.get("login", ""),
            "pass": creds.get("password", ""),
            "orderno": invoice_id,
        })
        return f"{base}print/?{params}"

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

        # Build enclosure with service markers
        service_markers: list[str] = []
        if order_data.get("fragile"):
            service_markers.append("ХРУПКИЙ")
        if order_data.get("call_before_delivery"):
            service_markers.append("ПОЗВОНИТЬ ПЕРЕД ДОСТАВКОЙ")
        if order_data.get("insurance"):
            service_markers.append("СТРАХОВАНИЕ")
        all_parts = service_markers + descriptions
        enclosure = _esc("; ".join(all_parts) if all_parts else "Посылка")

        # Declared value for insurance (Exline field: <inshprice>)
        declared_value = order_data.get("declared_value", 0)
        inshprice_tag = (
            f"    <inshprice>{float(declared_value):.2f}</inshprice>\n"
            if declared_value
            else ""
        )

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
{inshprice_tag}    <enclosure>{enclosure}</enclosure>
  </order>
</neworder>"""

        root = self._post_xml(xml, self._api_url(creds))

        # Exline wraps result in <createorder> child, not root attributes
        # NOTE: must use "is not None" — empty XML elements are falsy in ElementTree
        found = root.find("createorder")
        node = found if found is not None else root

        error = node.attrib.get("error", "1")
        errormsg = node.attrib.get("errormsg", node.attrib.get("errormsgru", ""))
        orderno = node.attrib.get("orderno", "")
        barcode = node.attrib.get("barcode", orderno)

        if not orderno:
            raise RuntimeError(
                f"Exline error {error}: {errormsg or 'no orderno returned'}. "
                f"Response: {ET.tostring(root, encoding='unicode')}"
            )

        if error != "0":
            logger.warning("Exline returned orderno=%s with non-zero error=%s: %s", orderno, error, errormsg)

        logger.info(
            "Exline invoice created: orderno=%s barcode=%s order_id=%s",
            orderno, barcode, order_id,
        )
        return InvoiceResult(
            waybill_number=barcode or orderno,
            carrier_invoice_id=orderno,
            waybill_pdf_bytes=None,
        )

    def get_invoice_pdf(self, invoice_id: str, creds: dict) -> bytes:
        try:
            import weasyprint
        except ImportError as exc:
            raise RuntimeError(
                "weasyprint не установлен: pip install weasyprint"
            ) from exc

        print_url = self._get_print_url(invoice_id, creds)
        resp = httpx.get(print_url, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()

        # Exline's /print/ redirects to session login when URL-based auth fails.
        # Detect this early so we don't save a login-page PDF as the waybill.
        final_url = str(resp.url)
        if "login" in final_url or "auth" in final_url:
            raise RuntimeError(
                f"Exline print page requires web session auth — "
                f"got redirected to login page (orderno={invoice_id}). "
                "URL-based credentials are only accepted by the XML API, not the web UI."
            )

        html_snippet = resp.text[:500].lower()
        if "войти" in html_snippet or ("login" in html_snippet and "password" in html_snippet):
            raise RuntimeError(
                f"Exline print page returned a login form instead of the waybill (orderno={invoice_id})"
            )

        pdf_bytes: bytes = weasyprint.HTML(
            string=resp.text,
            base_url=print_url,
        ).write_pdf()

        logger.info(
            "Exline: PDF сгенерирован для накладной invoice_id=%s size=%d bytes",
            invoice_id, len(pdf_bytes),
        )
        return pdf_bytes

    def cancel_invoice(self, invoice_id: str, creds: dict) -> bool:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<cancelorder>
  {self._auth_tag(creds)}
  <orderno>{_esc(invoice_id)}</orderno>
</cancelorder>"""
        try:
            root = self._post_xml(xml, self._api_url(creds))
            success = root.attrib.get("error", "1") == "0"
            if not success:
                logger.warning(
                    "Exline cancel_invoice failed: %s",
                    root.attrib.get("errormsg", ""),
                )
            return success
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

    def test_connection(self, creds: dict) -> bool:
        today = date.today().isoformat()
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<statusreq>
  {self._auth_tag(creds)}
  <datefrom>{today}</datefrom>
  <dateto>{today}</dateto>
  <limit>1</limit>
</statusreq>"""
        root = self._post_xml(xml, self._api_url(creds))
        error = root.attrib.get("error", "0")
        if error == "1":
            raise RuntimeError("Exline: ошибка авторизации (error=1)")
        return True
