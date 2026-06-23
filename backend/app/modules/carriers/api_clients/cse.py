"""
CSE (Courier Service Express) SOAP API client.

Protocol: SOAP over HTTP, XML UTF-8.
WSDL: http://web.cse.ru/1c/ws/Web1C.1cws?wsdl
Namespace: http://www.cargo3.ru  (confirmed from WSDL targetNamespace)

Credentials via CarrierAPICredentials.extra_config:
    login    — API login (test creds: "test")
    password — API password (test creds: "2016")
api_url — SOAP endpoint (default: http://web.cse.ru/1c/ws/Web1C.1cws)
"""
from __future__ import annotations

import base64
import logging
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import httpx

from app.modules.carriers.api_clients.base import CarrierAPIClient, InvoiceResult

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://web.cse.ru/1c/ws/Web1C.1cws"

_NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
_NS_M = "http://www.cargo3.ru"
_NM = f"{{{_NS_M}}}"

_TIMEOUT = 30
_CALC_TIMEOUT = 10

# In-process cache for TypesOfCargo GUID keyed by login (stable reference data)
_cargo_type_guid_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# XML helpers (also imported by tariff_engine for async calls)
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def build_envelope(method: str, inner: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        f' xmlns:m="{_NS_M}">'
        "<soap:Body>"
        f"<m:{method}>{inner}</m:{method}>"
        "</soap:Body>"
        "</soap:Envelope>"
    ).encode()


def extract_return(text: str, method: str) -> ET.Element:
    """Parse SOAP response XML and return the <m:return> element.
    Raises RuntimeError if the response contains an Error=true Properties block."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"CSE: invalid XML in {method} response: {exc}") from exc

    body = root.find(f"{{{_NS_SOAP}}}Body")
    if body is None:
        raise ValueError(f"CSE: no SOAP Body in {method} response")

    # SOAP Fault
    fault = body.find(f"{{{_NS_SOAP}}}Fault")
    if fault is not None:
        msg = (fault.findtext("faultstring") or "").strip()
        raise RuntimeError(f"CSE SOAP Fault in {method}: {msg}")

    # Try with namespace first, then without (use `is None` — ET.Element is falsy when childless)
    resp_el = body.find(f"{_NM}{method}Response")
    if resp_el is None:
        resp_el = body.find(f"{method}Response")
    if resp_el is None:
        raise ValueError(f"CSE: no {method}Response element in SOAP body")

    return_el = resp_el.find(f"{_NM}return")
    if return_el is None:
        return_el = resp_el.find("return")
    if return_el is None:
        raise ValueError(f"CSE: no <return> in {method}Response")

    # Check for application-level error: <m:Properties><m:Key>Error</m:Key><m:Value>true</m:Value>
    for prop in return_el.findall(f"{_NM}Properties"):
        key_el = prop.find(f"{_NM}Key")
        val_el = prop.find(f"{_NM}Value")
        if key_el is not None and (key_el.text or "") == "Error":
            if val_el is not None and (val_el.text or "").lower() in ("true", "1"):
                desc = ""
                for list_el in prop.findall(f"{_NM}List"):
                    lk = list_el.find(f"{_NM}Key")
                    lv = list_el.find(f"{_NM}Value")
                    if lk is not None and (lk.text or "") == "Description" and lv is not None:
                        desc = (lv.text or "").strip()
                code_map = {
                    "02011": "Неверный логин или пароль (ошибка авторизации CSE)",
                    "03010": "Пункт маршрута не найден (неверный geography GUID)",
                }
                human = code_map.get(desc, f"код {desc}")
                raise RuntimeError(f"CSE {method} error: {human}")

    return return_el


def find_text(el: ET.Element, tag: str) -> str:
    child = el.find(f"{_NM}{tag}")
    return (child.text or "").strip() if child is not None else ""


def fields_of(el: ET.Element) -> dict[str, Any]:
    """Extract m:Fields children into a flat dict with type coercion."""
    result: dict[str, Any] = {}
    for field_el in el.findall(f"{_NM}Fields"):
        k = find_text(field_el, "Key")
        if not k:
            continue
        v: Any = find_text(field_el, "Value")
        vtype = find_text(field_el, "ValueType")
        if vtype == "int" and v:
            try:
                v = int(v)
            except ValueError:
                pass
        elif vtype == "float" and v:
            try:
                v = float(v)
            except ValueError:
                pass
        elif vtype == "bool" and v:
            v = v.lower() in ("true", "1", "да")
        result[k] = v
    return result


def list_items(el: ET.Element) -> list[ET.Element]:
    return el.findall(f"{_NM}List")


def parse_calc_response(ret: ET.Element) -> list[dict]:
    """
    Parse the <return> element from a Calc SOAP response.

    Structure: return → List(Destination) → List(Tariff) → Fields
    Returns a list of tariff dicts with keys:
        tariff_guid, service_name, price, currency, min_days, max_days
    """
    tariffs: list[dict] = []
    for dest_item in list_items(ret):
        for tariff_item in list_items(dest_item):
            f = fields_of(tariff_item)
            tariff_guid = find_text(tariff_item, "Key")
            total = f.get("Total") or f.get("Price") or f.get("Summa")
            service_name = (
                f.get("Service") or f.get("ServiceName") or f.get("TariffName") or "CSE"
            )
            min_period = f.get("MinPeriod") or f.get("MinDays") or f.get("PeriodMin")
            max_period = f.get("MaxPeriod") or f.get("MaxDays") or f.get("PeriodMax")
            currency = f.get("CurrencyName") or f.get("Currency") or "RUB"

            if total is None:
                continue
            try:
                price = float(total)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            tariffs.append({
                "tariff_guid": tariff_guid,
                "service_name": str(service_name),
                "price": price,
                "currency": str(currency),
                "min_days": int(min_period) if min_period is not None else 3,
                "max_days": int(max_period) if max_period is not None else 10,
            })
    return tariffs


# ---------------------------------------------------------------------------
# CSE API client
# ---------------------------------------------------------------------------

class CSEAPIClient(CarrierAPIClient):
    carrier_code = "cse"

    # ── credentials helpers ──────────────────────────────────────────────────

    @staticmethod
    def _url(creds: dict) -> str:
        return (creds.get("api_url") or DEFAULT_API_URL).rstrip("/")

    @staticmethod
    def _login(creds: dict) -> str:
        return creds.get("login", "")

    @staticmethod
    def _password(creds: dict) -> str:
        return creds.get("password", "")

    # ── low-level sync POST ──────────────────────────────────────────────────

    def _post(self, method: str, inner: str, creds: dict, timeout: int = _TIMEOUT) -> ET.Element:
        resp = httpx.post(
            self._url(creds),
            content=build_envelope(method, inner),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{_NS_M}#WebService:{method}"',
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return extract_return(resp.text, method)

    # ── auth prefix used in most method bodies ───────────────────────────────

    def _auth(self, creds: dict) -> str:
        return (
            f"<m:login>{_esc(self._login(creds))}</m:login>"
            f"<m:password>{_esc(self._password(creds))}</m:password>"
        )

    # ── TypesOfCargo (cached) ────────────────────────────────────────────────

    def _types_of_cargo(self, creds: dict) -> list[dict]:
        inner = (
            self._auth(creds)
            + "<m:parameters><m:Key>TypesOfCargo</m:Key></m:parameters>"
        )
        ret = self._post("GetReferenceData", inner, creds)
        return [
            {
                "guid": find_text(item, "Key"),
                "name": find_text(item, "Value"),
                "is_default": fields_of(item).get("Default", False),
            }
            for item in list_items(ret)
        ]

    def _cargo_type_guid(self, creds: dict) -> str:
        cache_key = creds.get("login", "")
        if cache_key in _cargo_type_guid_cache:
            return _cargo_type_guid_cache[cache_key]
        types = self._types_of_cargo(creds)
        guid: str | None = None
        for t in types:
            if t.get("is_default"):
                guid = t["guid"]
                break
        if guid is None:
            for keyword in ("груз", "cargo", "посылк", "parcel"):
                for t in types:
                    if keyword in t.get("name", "").lower():
                        guid = t["guid"]
                        break
                if guid:
                    break
        if guid is None and types:
            guid = types[0]["guid"]
        if guid is None:
            raise RuntimeError("CSE: cannot resolve TypeOfCargo GUID")
        _cargo_type_guid_cache[cache_key] = guid
        return guid

    # ── Geography ────────────────────────────────────────────────────────────

    def search_geography(self, search: str, creds: dict) -> list[dict]:
        """Search CSE Geography by name / postcode / FIAS. Returns [{guid, name, parent, type, fias}]."""
        inner = (
            self._auth(creds)
            + "<m:parameters>"
            + "<m:Key>Geography</m:Key>"
            + f"<m:Fields><m:Key>Search</m:Key><m:Value>{_esc(search)}</m:Value></m:Fields>"
            + "</m:parameters>"
        )
        ret = self._post("GetReferenceData", inner, creds)
        results = []
        for item in list_items(ret):
            f = fields_of(item)
            results.append({
                "guid": find_text(item, "Key"),
                "name": find_text(item, "Value"),
                "parent": f.get("ParentName", ""),
                "type": f.get("Type", ""),
                "fias": f.get("FIAS", ""),
                "iata": f.get("IATA", ""),
            })
        return results

    # ── PVZ ──────────────────────────────────────────────────────────────────

    def get_pvz(self, creds: dict, geography_guid: str | None = None) -> list[dict]:
        """List pickup/delivery points. Optionally filter by city GUID."""
        params = "<m:Key>pvz</m:Key>"
        if geography_guid:
            params += f"<m:Fields><m:Key>InGroup</m:Key><m:Value>{_esc(geography_guid)}</m:Value></m:Fields>"
        inner = (
            self._auth(creds)
            + f"<m:parameters>{params}</m:parameters>"
        )
        ret = self._post("GetReferenceData", inner, creds)
        results = []
        for item in list_items(ret):
            f = fields_of(item)
            results.append({
                "guid": find_text(item, "Key"),
                "address": find_text(item, "Value"),
                "city": f.get("City", ""),
                "lat": f.get("Latitude", ""),
                "lon": f.get("Longitude", ""),
                "schedule": f.get("Schedule", ""),
                "phone": f.get("Phone", ""),
                "type": f.get("Type", ""),
            })
        return results

    # ── Delivery info ─────────────────────────────────────────────────────────

    def get_delivery_info(
        self,
        from_geo: str,
        to_geo: str,
        creds: dict,
        cargo_type_guid: str | None = None,
    ) -> dict:
        """Get transit times, COD/card availability for a route."""
        if not cargo_type_guid:
            try:
                cargo_type_guid = self._cargo_type_guid(creds)
            except Exception:
                cargo_type_guid = ""
        inner = (
            self._auth(creds)
            + "<m:parameters>"
            + "<m:Key>deliveryinfo</m:Key>"
            + f"<m:Fields><m:Key>SenderGeography</m:Key><m:Value>{_esc(from_geo)}</m:Value></m:Fields>"
            + f"<m:Fields><m:Key>RecipientGeography</m:Key><m:Value>{_esc(to_geo)}</m:Value></m:Fields>"
            + f"<m:Fields><m:Key>TypeOfCargo</m:Key><m:Value>{_esc(cargo_type_guid)}</m:Value></m:Fields>"
            + "</m:parameters>"
        )
        ret = self._post("GetReferenceData", inner, creds)
        f = fields_of(ret)
        return {
            "min_days": f.get("MinDays") or f.get("MinPeriod"),
            "max_days": f.get("MaxDays") or f.get("MaxPeriod"),
            "cod_available": bool(f.get("COD", False)),
            "card_available": bool(f.get("CardPayment", False)),
            "services": [
                {"guid": find_text(s, "Key"), "name": find_text(s, "Value")}
                for s in list_items(ret)
            ],
        }

    # ── Available delivery dates ──────────────────────────────────────────────

    def get_available_delivery_dates(
        self,
        from_geo: str,
        to_geo: str,
        creds: dict,
        urgency_guid: str | None = None,
    ) -> list[dict]:
        """Available delivery date/time slots for a route."""
        today = date.today().isoformat()
        params = (
            "<m:Key>availabledeliverydates</m:Key>"
            f"<m:Fields><m:Key>Search</m:Key><m:Value>{_esc(to_geo)}</m:Value></m:Fields>"
            f"<m:Fields><m:Key>Geography</m:Key><m:Value>{_esc(from_geo)}</m:Value></m:Fields>"
            f"<m:Fields><m:Key>takedate</m:Key><m:Value>{today}</m:Value></m:Fields>"
        )
        if urgency_guid:
            params += f"<m:Fields><m:Key>other</m:Key><m:Value>{_esc(urgency_guid)}</m:Value></m:Fields>"
        inner = (
            self._auth(creds)
            + f"<m:parameters>{params}</m:parameters>"
        )
        ret = self._post("GetReferenceData", inner, creds)
        results = []
        for item in list_items(ret):
            f = fields_of(item)
            slots = [
                {"from": find_text(s, "Key"), "to": find_text(s, "Value")}
                for s in list_items(item)
            ]
            results.append({
                "date": find_text(item, "Key"),
                "time_from": f.get("TimeFrom", ""),
                "time_to": f.get("TimeTo", ""),
                "slots": slots,
            })
        return results

    # ── Available take dates ──────────────────────────────────────────────────

    def get_available_take_dates(
        self,
        from_geo: str,
        creds: dict,
        urgency_guid: str | None = None,
    ) -> list[dict]:
        """Available courier pickup date/time slots from origin city."""
        params = (
            "<m:Key>availabletakedates</m:Key>"
            f"<m:Fields><m:Key>Geography</m:Key><m:Value>{_esc(from_geo)}</m:Value></m:Fields>"
        )
        if urgency_guid:
            params += f"<m:Fields><m:Key>other</m:Key><m:Value>{_esc(urgency_guid)}</m:Value></m:Fields>"
        inner = (
            self._auth(creds)
            + f"<m:parameters>{params}</m:parameters>"
        )
        ret = self._post("GetReferenceData", inner, creds)
        results = []
        for item in list_items(ret):
            slots = [
                {"from": find_text(s, "Key"), "to": find_text(s, "Value")}
                for s in list_items(item)
            ]
            results.append({"date": find_text(item, "Key"), "slots": slots})
        return results

    # ── GetDocuments ──────────────────────────────────────────────────────────

    def get_documents(self, waybill_number: str, creds: dict) -> dict:
        """Fetch full data for a waybill by number."""
        inner = (
            self._auth(creds)
            + "<m:data>"
            + "<m:Key>Documents</m:Key>"
            + "<m:List>"
            + "<m:Key>Document</m:Key>"
            + f"<m:Fields><m:Key>Number</m:Key><m:Value>{_esc(waybill_number)}</m:Value></m:Fields>"
            + "</m:List>"
            + "</m:data>"
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:Fields><m:Key>DocumentType</m:Key><m:Value>Waybill</m:Value></m:Fields>"
            + "</m:parameters>"
        )
        ret = self._post("GetDocuments", inner, creds)
        f = fields_of(ret)
        return {
            "number": f.get("Number", waybill_number),
            "status": f.get("Status", ""),
            "sender": f.get("Sender", ""),
            "recipient": f.get("Recipient", ""),
            "weight": f.get("Weight"),
            "created_at": f.get("Date", ""),
        }

    # ── DeleteDocuments ───────────────────────────────────────────────────────

    def delete_document(
        self,
        waybill_number: str,
        reason: str,
        contact: str,
        phone: str,
        creds: dict,
    ) -> bool:
        """Cancel a waybill. Returns True on success."""
        inner = (
            self._auth(creds)
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:Fields><m:Key>DocumentType</m:Key><m:Value>Waybill</m:Value></m:Fields>"
            + f"<m:Fields><m:Key>Number</m:Key><m:Value>{_esc(waybill_number)}</m:Value></m:Fields>"
            + f"<m:Fields><m:Key>Reason</m:Key><m:Value>{_esc(reason)}</m:Value></m:Fields>"
            + f"<m:Fields><m:Key>ClientContact</m:Key><m:Value>{_esc(contact)}</m:Value></m:Fields>"
            + f"<m:Fields><m:Key>Phone</m:Key><m:Value>{_esc(phone)}</m:Value></m:Fields>"
            + "</m:parameters>"
        )
        try:
            ret = self._post("DeleteDocuments", inner, creds)
            f = fields_of(ret)
            error = f.get("Error", f.get("ErrorCode", ""))
            return str(error) in ("", "0")
        except Exception as exc:
            logger.warning("CSE delete_document failed (waybill=%s): %s", waybill_number, exc)
            return False

    # ── GetFormsForDocuments ──────────────────────────────────────────────────

    def get_print_form(self, waybill_number: str, creds: dict) -> bytes:
        """Download PDF print form of a waybill. Returns raw PDF bytes."""
        inner = (
            self._auth(creds)
            + "<m:documents>"
            + "<m:Key>Documents</m:Key>"
            + "<m:List>"
            + "<m:Key>Document</m:Key>"
            + f"<m:Fields><m:Key>Number</m:Key><m:Value>{_esc(waybill_number)}</m:Value></m:Fields>"
            + "</m:List>"
            + "</m:documents>"
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:Fields><m:Key>DocumentType</m:Key><m:Value>Waybill</m:Value></m:Fields>"
            + "<m:Fields><m:Key>Type</m:Key><m:Value>print</m:Value></m:Fields>"
            + "<m:Fields><m:Key>Format</m:Key><m:Value>pdf</m:Value></m:Fields>"
            + "</m:parameters>"
        )
        ret = self._post("GetFormsForDocuments", inner, creds, timeout=_TIMEOUT)
        # PDF is in BData field (base64) on each document item
        for item in list_items(ret):
            bdata = fields_of(item).get("BData", "") or find_text(item, "BData")
            if bdata:
                return base64.b64decode(bdata)
        # Sometimes BData is directly on return element
        bdata = find_text(ret, "BData")
        if bdata:
            return base64.b64decode(bdata)
        raise RuntimeError(f"CSE: no PDF data returned for waybill {waybill_number}")

    # ── Tracking ──────────────────────────────────────────────────────────────

    def tracking(self, waybill_number: str, creds: dict) -> list[dict]:
        """Get status event history for a waybill."""
        inner = (
            self._auth(creds)
            + "<m:documents>"
            + "<m:Key>Documents</m:Key>"
            + "<m:List>"
            + "<m:Key>Document</m:Key>"
            + f"<m:Fields><m:Key>Number</m:Key><m:Value>{_esc(waybill_number)}</m:Value></m:Fields>"
            + "</m:List>"
            + "</m:documents>"
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:Fields><m:Key>DocumentType</m:Key><m:Value>Waybill</m:Value></m:Fields>"
            + "</m:parameters>"
        )
        ret = self._post("Tracking", inner, creds)
        events: list[dict] = []
        for doc_item in list_items(ret):
            for status_item in list_items(doc_item):
                f = fields_of(status_item)
                events.append({
                    "guid": find_text(status_item, "Key"),
                    "status": f.get("StatusName") or f.get("Status", ""),
                    "occurred_at": f.get("DateTime") or f.get("Date", ""),
                    "location": f.get("Location", ""),
                    "comment": f.get("Comment", ""),
                    "recipient": f.get("RecipientName", ""),
                })
        return events

    # ── Calc ──────────────────────────────────────────────────────────────────

    def calc(
        self,
        from_geo: str,
        to_geo: str,
        weight: float,
        qty: int,
        creds: dict,
        cargo_type_guid: str | None = None,
    ) -> list[dict]:
        """Calculate delivery cost. Returns list of tariff dicts."""
        if not cargo_type_guid:
            try:
                cargo_type_guid = self._cargo_type_guid(creds)
            except Exception as exc:
                logger.warning("CSE: cargo type GUID unavailable (%s), proceeding without it", exc)
                cargo_type_guid = ""
        inner = _build_calc_inner(
            self._login(creds), self._password(creds),
            from_geo, to_geo, weight, qty, cargo_type_guid,
        )
        ret = self._post("Calc", inner, creds, timeout=_CALC_TIMEOUT)
        return parse_calc_response(ret)

    # ── SaveWaybillOffice ─────────────────────────────────────────────────────

    def create_waybill(self, order_data: dict, creds: dict) -> str:
        """
        Create a waybill via SaveWaybillOffice. Returns the waybill number string.

        order_data keys:
            sender      — dict with full_name, phone, city/geography_guid, address
            recipient   — same
            packages    — list of {weight_kg, quantity, description}
            take_date   — YYYY-MM-DD string (defaults to today)
        """
        sender = order_data.get("sender", {})
        recipient = order_data.get("recipient", {})
        packages = order_data.get("packages", [])

        total_weight = sum(p.get("weight_kg", 0) * p.get("quantity", 1) for p in packages)
        total_qty = sum(p.get("quantity", 1) for p in packages)
        desc_parts = [p["description"] for p in packages if p.get("description")]
        description = "; ".join(desc_parts) if desc_parts else "Посылка"
        take_date = order_data.get("take_date", date.today().isoformat())

        sender_geo = sender.get("geography_guid") or sender.get("city", "")
        recipient_geo = recipient.get("geography_guid") or recipient.get("city", "")

        order_xml = (
            f"<m:TakeDate>{_esc(take_date)}</m:TakeDate>"
            "<m:Sender>"
            f"<m:Name>{_esc(sender.get('full_name', ''))}</m:Name>"
            f"<m:Phone>{_esc(sender.get('phone', ''))}</m:Phone>"
            f"<m:Geography>{_esc(sender_geo)}</m:Geography>"
            f"<m:Address>{_esc(sender.get('address', sender.get('address_line1', '')))}</m:Address>"
            "</m:Sender>"
            "<m:Recipient>"
            f"<m:Name>{_esc(recipient.get('full_name', ''))}</m:Name>"
            f"<m:Phone>{_esc(recipient.get('phone', ''))}</m:Phone>"
            f"<m:Geography>{_esc(recipient_geo)}</m:Geography>"
            f"<m:Address>{_esc(recipient.get('address', recipient.get('address_line1', '')))}</m:Address>"
            "</m:Recipient>"
            f"<m:Weight>{round(float(total_weight), 3)}</m:Weight>"
            f"<m:Quantity>{int(total_qty)}</m:Quantity>"
            f"<m:Description>{_esc(description)}</m:Description>"
            "<m:TypeOfPayer>Sender</m:TypeOfPayer>"
            "<m:WayOfPayment>NonCash</m:WayOfPayment>"
        )

        # SaveWaybillOffice uses capital-case Login/Password (different from other methods)
        login = _esc(self._login(creds))
        pwd = _esc(self._password(creds))
        inner = (
            "<m:Language>ru</m:Language>"
            f"<m:Login>{login}</m:Login>"
            f"<m:Password>{pwd}</m:Password>"
            "<m:Company></m:Company>"
            "<m:Number></m:Number>"
            "<m:ClientNumber></m:ClientNumber>"
            f"<m:OrderData>{order_xml}</m:OrderData>"
            "<m:Office></m:Office>"
        )
        ret = self._post("SaveWaybillOffice", inner, creds)

        # resultstring — waybill number or error message as text
        result_text = (ret.text or "").strip()
        if result_text:
            if "ошибк" in result_text.lower() or "error" in result_text.lower():
                raise RuntimeError(f"CSE SaveWaybillOffice error: {result_text}")
            return result_text

        # Fallback: try first List item key as waybill number
        for item in list_items(ret):
            num = find_text(item, "Key") or find_text(item, "Value")
            if num:
                return num

        raise RuntimeError("CSE: SaveWaybillOffice returned no waybill number")

    # ── CarrierAPIClient interface ───────────────────────────────────────────

    def create_invoice(self, order_data: dict, creds: dict) -> InvoiceResult:
        waybill_number = self.create_waybill(order_data, creds)
        logger.info(
            "CSE invoice created: waybill=%s order_id=%s",
            waybill_number, order_data.get("order_id"),
        )
        pdf_bytes: bytes | None = None
        try:
            pdf_bytes = self.get_print_form(waybill_number, creds)
        except Exception as exc:
            logger.warning("CSE PDF fetch failed (non-fatal): %s", exc)
        return InvoiceResult(
            waybill_number=waybill_number,
            carrier_invoice_id=waybill_number,
            waybill_pdf_bytes=pdf_bytes,
        )

    def get_invoice_pdf(self, invoice_id: str, creds: dict) -> bytes:
        return self.get_print_form(invoice_id, creds)

    def cancel_invoice(self, invoice_id: str, creds: dict) -> bool:
        return self.delete_document(
            waybill_number=invoice_id,
            reason="Отмена клиентом",
            contact="Novex",
            phone=creds.get("contact_phone", "+70000000000"),
            creds=creds,
        )

    def test_connection(self, creds: dict) -> bool:
        """Test CSE connectivity and credentials.
        Step 1: Ping (no auth) — verifies network/endpoint.
        Step 2: GetReferenceData TypesOfCargo — verifies credentials.
        """
        try:
            # Step 1: Ping
            ping_resp = httpx.post(
                self._url(creds),
                content=build_envelope("Ping", ""),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=_TIMEOUT,
            )
            ping_ret = extract_return(ping_resp.text, "Ping")
            if (ping_ret.text or "").strip().lower() != "true":
                raise RuntimeError("CSE Ping returned non-true response")

            # Step 2: Auth check
            self._types_of_cargo(creds)
            return True
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"CSE HTTP {exc.response.status_code}: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"CSE connection test failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Internal helper used by both sync client and async tariff_engine
# ---------------------------------------------------------------------------

def _build_calc_inner(
    login: str,
    password: str,
    from_geo: str,
    to_geo: str,
    weight: float,
    qty: int,
    cargo_type_guid: str,
) -> str:
    return (
        f"<m:login>{_esc(login)}</m:login>"
        f"<m:password>{_esc(password)}</m:password>"
        "<m:data>"
        "<m:Key>Destinations</m:Key>"
        "<m:List>"
        "<m:Key>Destination</m:Key>"
        f"<m:Fields><m:Key>SenderGeography</m:Key><m:Value>{_esc(from_geo)}</m:Value></m:Fields>"
        f"<m:Fields><m:Key>RecipientGeography</m:Key><m:Value>{_esc(to_geo)}</m:Value></m:Fields>"
        f"<m:Fields><m:Key>TypeOfCargo</m:Key><m:Value>{_esc(cargo_type_guid)}</m:Value></m:Fields>"
        f"<m:Fields><m:Key>Weight</m:Key><m:Value>{weight:.3f}</m:Value>"
        "<m:ValueType>float</m:ValueType></m:Fields>"
        f"<m:Fields><m:Key>Qty</m:Key><m:Value>{qty}</m:Value>"
        "<m:ValueType>int</m:ValueType></m:Fields>"
        "</m:List>"
        "</m:data>"
        "<m:parameters><m:Key>Parameters</m:Key></m:parameters>"
    )
