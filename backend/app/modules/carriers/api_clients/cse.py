"""
CSE (Courier Service Express) SOAP API client.

Protocol: SOAP over HTTP, XML UTF-8.
WSDL: http://lk-test.cse.ru/1c/ws/web1c.1cws?wsdl  (test)
      http://web.cse.ru/1c/ws/Web1C.1cws?wsdl        (prod)
Namespace: http://www.cargo3.ru

Credentials via CarrierAPICredentials.extra_config:
    login    — API login (test creds: "test")
    password — API password (test creds: "2016")
    api_url  — SOAP endpoint (default: prod URL below)
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
TEST_API_URL = "http://lk-test.cse.ru/1c/ws/web1c.1cws"

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
        "<soap:Header/>"
        "<soap:Body>"
        f"<m:{method}>{inner}</m:{method}>"
        "</soap:Body>"
        "</soap:Envelope>"
    ).encode()


def _list_item(key: str, value: str, vtype: str = "string") -> str:
    """Build a single <m:List> param item for GetReferenceData parameters."""
    return (
        "<m:List>"
        f"<m:Key>{_esc(key)}</m:Key>"
        f"<m:Value>{_esc(value)}</m:Value>"
        f"<m:ValueType>{vtype}</m:ValueType>"
        "</m:List>"
    )


def _ref_params(reference: str, *extras: tuple[str, str, str]) -> str:
    """
    Build the <m:parameters> block for GetReferenceData.

    Per CSE API docs: parameters must have Key='parameters' and all
    actual params passed as List items (Key/Value/ValueType).
    """
    body = (
        "<m:parameters>"
        "<m:Key>parameters</m:Key>"
        + _list_item("Reference", reference)
    )
    for key, value, vtype in extras:
        body += _list_item(key, value, vtype)
    body += "</m:parameters>"
    return body


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

    fault = body.find(f"{{{_NS_SOAP}}}Fault")
    if fault is not None:
        msg = (fault.findtext("faultstring") or "").strip()
        raise RuntimeError(f"CSE SOAP Fault in {method}: {msg}")

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

    # Check for application-level error
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
                # 02011 = auth error per CSE error code registry
                code_map = {
                    "02011": "Неверный логин или пароль (ошибка авторизации CSE)",
                    "02053": "По указанным данным информация не найдена",
                    "03010": "Пункт маршрута не найден (неверный geography GUID)",
                    "05011": "Указан некорректный код срочности",
                    "05042": "Указан некорректный код географии",
                }
                human = code_map.get(desc, f"код {desc}" if desc else "неизвестная ошибка")
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
        if vtype in ("int",) and v:
            try:
                v = int(float(v))
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


def props_of(el: ET.Element) -> list[ET.Element]:
    return el.findall(f"{_NM}Properties")


def parse_calc_response(ret: ET.Element) -> list[dict]:
    """
    Parse the <return> element from a Calc SOAP response.

    Structure: return → List(Destination) → List(Tariff) → Fields
    Returns a list of tariff dicts.
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

            urgency_guid = f.get("Urgency", "")

            tariffs.append({
                "tariff_guid": tariff_guid,
                "service_name": str(service_name),
                "price": price,
                "currency": str(currency),
                "min_days": int(min_period) if min_period is not None else 3,
                "max_days": int(max_period) if max_period is not None else 10,
                "urgency_guid": urgency_guid,
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
            headers={"Content-Type": "text/xml; charset=utf-8"},
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
        inner = self._auth(creds) + _ref_params("TypesOfCargo")
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
        inner = self._auth(creds) + _ref_params(
            "Geography",
            ("Search", search, "string"),
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
        extras: list[tuple[str, str, str]] = []
        if geography_guid:
            extras.append(("Ingroup", geography_guid, "string"))
        inner = self._auth(creds) + _ref_params("pvz", *extras)
        ret = self._post("GetReferenceData", inner, creds)
        results = []
        for item in list_items(ret):
            f = fields_of(item)
            results.append({
                "guid": find_text(item, "Key"),
                "address": f.get("Address", find_text(item, "Value")),
                "city": f.get("NameGeography", f.get("Geography", "")),
                "phone": f.get("Phone", ""),
                "type": f.get("TypeOfPVZ", ""),
                "code": f.get("CodePVZ", ""),
            })
        return results

    # ── Delivery info ─────────────────────────────────────────────────────────

    def get_delivery_info(
        self,
        from_geo: str,
        to_geo: str,
        creds: dict,
        urgency_guid: str | None = None,
    ) -> dict:
        """Get transit times and COD availability for a route."""
        extras: list[tuple[str, str, str]] = [
            ("Search", to_geo, "string"),
            ("geography", from_geo, "string"),
        ]
        if urgency_guid:
            extras.append(("other", urgency_guid, "string"))
        inner = self._auth(creds) + _ref_params("deliveryinfo", *extras)
        ret = self._post("GetReferenceData", inner, creds)
        # Response: return > List(Data) > Fields
        result: dict[str, Any] = {
            "min_days": None,
            "max_days": None,
            "cod_available": False,
            "card_available": False,
            "services": [],
        }
        for item in list_items(ret):
            f = fields_of(item)
            if f.get("MinPeriod") is not None:
                result["min_days"] = f.get("MinPeriod")
            if f.get("MaxPeriod") is not None:
                result["max_days"] = f.get("MaxPeriod")
            if f.get("COD") is not None:
                result["cod_available"] = bool(f.get("COD"))
            if f.get("PaymentByRecipient") is not None:
                result["card_available"] = bool(f.get("PaymentByRecipient"))
            urgency = f.get("Urgency", "")
            desc = f.get("UrgencyDescription", "")
            if urgency:
                result["services"].append({"guid": urgency, "name": desc})
        return result

    # ── Available delivery dates ──────────────────────────────────────────────

    def get_available_delivery_dates(
        self,
        from_geo: str,
        to_geo: str,
        creds: dict,
        urgency_guid: str | None = None,
    ) -> list[dict]:
        """Available delivery date/time slots for a route."""
        today = date.today().isoformat() + "T00:00:00"
        extras: list[tuple[str, str, str]] = [
            ("Search", to_geo, "string"),
            ("geography", from_geo, "string"),
            ("takedate", today, "dateTime"),
        ]
        if urgency_guid:
            extras.append(("other", urgency_guid, "string"))
        inner = self._auth(creds) + _ref_params("availabledeliverydates", *extras)
        ret = self._post("GetReferenceData", inner, creds)
        # Response: return > List(DeliveryDates) > Properties(Interval) > Fields(TimeFrom/TimeTo)
        results = []
        for item in list_items(ret):
            f = fields_of(item)
            date_val = f.get("DeliveryDate", find_text(item, "Key"))
            slots = []
            for prop in props_of(item):
                pf = fields_of(prop)
                time_from = pf.get("TimeFrom", "")
                time_to = pf.get("TimeTo", "")
                if time_from or time_to:
                    slots.append({"from": time_from, "to": time_to})
            results.append({
                "date": date_val,
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
        extras: list[tuple[str, str, str]] = [
            ("geography", from_geo, "string"),
        ]
        if urgency_guid:
            extras.append(("other", urgency_guid, "string"))
        inner = self._auth(creds) + _ref_params("availabletakedates", *extras)
        ret = self._post("GetReferenceData", inner, creds)
        # Response: return > List(TakeDates) > Properties(Interval) > Fields + Fields(TakeDate)
        results = []
        for item in list_items(ret):
            f = fields_of(item)
            date_val = f.get("TakeDate", find_text(item, "Key"))
            slots = []
            for prop in props_of(item):
                pf = fields_of(prop)
                time_from = pf.get("TimeFrom", "")
                time_to = pf.get("TimeTo", "")
                if time_from or time_to:
                    slots.append({"from": time_from, "to": time_to})
            results.append({"date": date_val, "slots": slots})
        return results

    # ── GetDocuments ──────────────────────────────────────────────────────────

    def get_documents(self, waybill_number: str, creds: dict) -> dict:
        """Fetch full data for a waybill by number."""
        inner = (
            self._auth(creds)
            + "<m:data>"
            + "<m:Key>Documents</m:Key>"
            + f"<m:List><m:Key>{_esc(waybill_number)}</m:Key></m:List>"
            + "</m:data>"
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:Properties>"
            + "<m:Key>DocumentType</m:Key>"
            + "<m:Value>Waybill</m:Value>"
            + "<m:ValueType>string</m:ValueType>"
            + "</m:Properties>"
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
            + f"<m:List><m:Key>{_esc(waybill_number)}</m:Key></m:List>"
            + "</m:documents>"
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:Properties><m:Key>DocumentType</m:Key><m:Value>Waybill</m:Value><m:ValueType>string</m:ValueType></m:Properties>"
            + "<m:Properties><m:Key>Type</m:Key><m:Value>print</m:Value><m:ValueType>string</m:ValueType></m:Properties>"
            + "<m:Properties><m:Key>Format</m:Key><m:Value>pdf</m:Value><m:ValueType>string</m:ValueType></m:Properties>"
            + "</m:parameters>"
        )
        ret = self._post("GetFormsForDocuments", inner, creds, timeout=_TIMEOUT)
        for item in list_items(ret):
            bdata = fields_of(item).get("BData", "") or find_text(item, "BData")
            if bdata:
                return base64.b64decode(bdata)
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
            + "<m:Properties>"
            + "<m:Key>DocumentType</m:Key>"
            + "<m:Value>Waybill</m:Value>"
            + "<m:ValueType>string</m:ValueType>"
            + "</m:Properties>"
            + f"<m:List><m:Key>{_esc(waybill_number)}</m:Key></m:List>"
            + "</m:documents>"
            + "<m:parameters><m:Key>Parameters</m:Key></m:parameters>"
        )
        ret = self._post("Tracking", inner, creds)
        events: list[dict] = []
        for doc_item in list_items(ret):
            # Status events are in Tables > List > List
            tables_el = doc_item.find(f"{_NM}Tables")
            if tables_el is not None:
                for table_item in list_items(tables_el):
                    for status_item in list_items(table_item):
                        p = {
                            (prop.find(f"{_NM}Key").text or "").strip(): (
                                prop.find(f"{_NM}Value").text or ""
                            ).strip()
                            for prop in props_of(status_item)
                            if prop.find(f"{_NM}Key") is not None
                        }
                        events.append({
                            "guid": p.get("GUID", ""),
                            "status": p.get("StatusName") or p.get("Status", ""),
                            "occurred_at": p.get("DateTime") or p.get("Date", ""),
                            "location": p.get("Location", ""),
                            "comment": p.get("Comment", ""),
                            "recipient": p.get("Recipient", ""),
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

        def _field(key: str, value: str, vtype: str = "string") -> str:
            return (
                f"<m:Fields><m:Key>{key}</m:Key>"
                f"<m:Value>{_esc(value)}</m:Value>"
                f"<m:ValueType>{vtype}</m:ValueType></m:Fields>"
            )

        order_xml = (
            _field("TakeDate", take_date, "dateTime")
            + _field("Sender", sender.get("full_name", ""))
            + _field("SenderPhone", sender.get("phone", ""))
            + _field("SenderGeography", sender_geo)
            + _field("SenderAddress", sender.get("address", sender.get("address_line1", "")))
            + _field("Recipient", recipient.get("full_name", ""))
            + _field("RecipientPhone", recipient.get("phone", ""))
            + _field("RecipientGeography", recipient_geo)
            + _field("RecipientAddress", recipient.get("address", recipient.get("address_line1", "")))
            + _field("Weight", f"{round(float(total_weight), 3)}", "float")
            + _field("Quantity", str(int(total_qty)), "int")
            + _field("Description", description)
            + _field("TypeOfPayer", "Sender")
            + _field("WayOfPayment", "1")
        )

        login = _esc(self._login(creds))
        pwd = _esc(self._password(creds))
        inner = (
            f"<m:login>{login}</m:login>"
            f"<m:password>{pwd}</m:password>"
            "<m:order>"
            + order_xml
            + "</m:order>"
        )
        ret = self._post("SaveWaybillOffice", inner, creds)

        result_text = (ret.text or "").strip()
        if result_text:
            if "ошибк" in result_text.lower() or "error" in result_text.lower():
                raise RuntimeError(f"CSE SaveWaybillOffice error: {result_text}")
            return result_text

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
            ping_resp = httpx.post(
                self._url(creds),
                content=build_envelope("Ping", ""),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=_TIMEOUT,
            )
            ping_ret = extract_return(ping_resp.text, "Ping")
            if (ping_ret.text or "").strip().lower() != "true":
                raise RuntimeError("CSE Ping returned non-true response")

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
