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

from app.modules.carriers.api_clients.base import CarrierAPIClient, CarrierServiceOption, InvoiceResult

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

def _prop(key: str, value: str) -> str:
    """Build a <m:Properties> element with string ValueType."""
    return (
        "<m:Properties>"
        f"<m:Key>{key}</m:Key>"
        f"<m:Value>{value}</m:Value>"
        "<m:ValueType>string</m:ValueType>"
        "</m:Properties>"
    )


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
        elif vtype in ("bool", "boolean") and v:
            v = v.lower() in ("true", "1", "да")
        result[k] = v
    return result


def list_items(el: ET.Element) -> list[ET.Element]:
    return el.findall(f"{_NM}List")


def props_of(el: ET.Element) -> list[ET.Element]:
    return el.findall(f"{_NM}Properties")


def _tracking_events_from(status_item: ET.Element) -> list[dict]:
    """Extract a single tracking event from an <m:List> node.

    Per CSE Tracking response format: the event's <m:Key> is the status name
    (Russian, e.g. "Заказ создан"), and its <m:Properties> children carry the
    metadata (GUID, Comment, RecorderGUID, RecorderName, DateTime, etc.).

    Returns [] for nodes that look like metadata (no DateTime property) so that
    the caller can iterate every List child without filtering upfront.
    """
    status_name = find_text(status_item, "Key")
    props: dict[str, str] = {}
    for prop in props_of(status_item):
        key_el = prop.find(f"{_NM}Key")
        val_el = prop.find(f"{_NM}Value")
        if key_el is None:
            continue
        key = (key_el.text or "").strip()
        value = (val_el.text or "").strip() if val_el is not None else ""
        if key:
            props[key] = value

    occurred_at = props.get("DateTime") or props.get("DeliveryDateTime") or ""
    if not occurred_at:
        return []

    return [{
        "guid": props.get("GUID", ""),
        "status": status_name,
        "occurred_at": occurred_at,
        "location": props.get("Location", ""),
        "comment": props.get("Comment", ""),
        "recipient": props.get("Recipient", ""),
        "recorder": props.get("RecorderName", ""),
    }]


# CSE Services reference GUIDs — the subset we currently expose to the user.
# CSE bills / applies these only when passed via <AdditionalServices><Items>.
# Discovered live via GetReferenceData:Services (see cse_geography audit).
_CSE_SERVICE_GUIDS: dict[str, str] = {
    "insurance":      "cc03d9ad-61f4-11dc-bda1-0015170f8c09",  # Страхование
    "declared_value": "6da21fe7-4f13-11dc-bda1-0015170f8c09",  # Объявленная стоимость
}


# CSE Currencies reference GUIDs → ISO 4217 code.
# Populated from GetReferenceData:Currencies on the CSE test endpoint.
# Only used as fallback if Calc omits CurrencyName; RUB stays the safe default.
_CSE_CURRENCY_GUID_TO_ISO: dict[str, str] = {
    "ff3f7c38-4430-11dc-9497-0015170f8c09": "RUB",
    "d3a2419e-e7e9-11e8-80c1-7cd30aec6901": "KZT",
    "e6853795-4421-11dc-9497-0015170f8c09": "USD",
    "e6853796-4421-11dc-9497-0015170f8c09": "EUR",
}


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

            # AdditionalService=true rows are add-on services (Страхование fee,
            # etc.), not base delivery tariffs — do not show them as tariff
            # options in the quote card.
            if f.get("AdditionalService") is True:
                continue

            tariff_guid = find_text(tariff_item, "Value")  # Key="Tariff" (constant); GUID is in Value
            total = f.get("Total") or f.get("Price") or f.get("Summa")
            # UrgencyName is the actual service level shown to the user
            # ("Срочная", "Стандартная", "Эконом доставка", …). "Service" in
            # Calc response is a Services-reference classification (e.g.
            # "Частичный выкуп") that is the same across all urgencies of one
            # contract — using it would collapse all rows to a single name.
            service_name = (
                f.get("UrgencyName")
                or f.get("ServiceName")
                or f.get("TariffName")
                or f.get("Service")
                or "CSE"
            )
            min_period = f.get("MinPeriod") or f.get("MinDays") or f.get("PeriodMin")
            max_period = f.get("MaxPeriod") or f.get("MaxDays") or f.get("PeriodMax")
            # Currency: Calc returns both GUID (Currency field) and ISO code
            # (CurrencyName). Prefer CurrencyName. GUID→ISO mapping via
            # GetReferenceData:Currencies is only a fallback if CurrencyName
            # is ever absent (default "RUB" matches CSE's default currency).
            currency = f.get("CurrencyName") or _CSE_CURRENCY_GUID_TO_ISO.get(
                (f.get("Currency") or "").strip(), "RUB"
            )

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
                # Per-tariff flags from Calc — reused by the tariff engine
                # to fill service availability without a second HTTP call.
                "cod": bool(f.get("COD")) if f.get("COD") is not None else None,
                "return_available": bool(f.get("Return")) if f.get("Return") is not None else None,
                "agent_delivery": bool(f.get("Agent")) if f.get("Agent") is not None else None,
                "urgency_description": (f.get("UrgencyDescription") or "").strip(),
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
        # Prefer "Груз" (freight/parcel) over "Документы" (documents is Default=true
        # but wrong for parcel shipments). Search keywords first, then fall back to default.
        for keyword in ("груз", "cargo", "посылк", "parcel"):
            for t in types:
                if keyword in t.get("name", "").lower():
                    guid = t["guid"]
                    break
            if guid:
                break
        if guid is None:
            for t in types:
                if t.get("is_default"):
                    guid = t["guid"]
                    break
        if guid is None and types:
            guid = types[0]["guid"]
        if guid is None:
            raise RuntimeError("CSE: cannot resolve TypeOfCargo GUID")
        _cargo_type_guid_cache[cache_key] = guid
        return guid

    # ── Geography ────────────────────────────────────────────────────────────

    def search_geography(
        self,
        search: str,
        creds: dict,
        country_code: str = "KZ",
        in_group: str = "",
    ) -> list[dict]:
        """Search CSE Geography by name / postcode.

        country_code: ISO 3166-1 alpha-2 code passed to the API and used for
        client-side filtering (default 'KZ' — Kazakhstan only).
        Pass None or '' to return all countries without filtering.

        in_group: optional GUID of a parent geography group. Passing
        Kazakhstan's country GUID ("d5d451af-442d-11dc-9497-0015170f8c09")
        scopes results to KZ entries only — the only way to enumerate all
        KZ cities via the Geography reference.
        """
        # KZ cities in CSE are stored with a trailing " г" suffix
        # ("Алматы г", "Астана г"). A plain "Алматы" search returns nothing,
        # so we retry with the suffix if the first pass is empty.
        def _do_search(term: str) -> ET.Element:
            extras: list[tuple[str, str, str]] = [("Search", term, "string")]
            if in_group:
                extras.append(("InGroup", in_group, "string"))
            inner = self._auth(creds) + _ref_params("Geography", *extras)
            return self._post("GetReferenceData", inner, creds)

        ret = _do_search(search)
        raw_items = list(list_items(ret))
        if not raw_items and search and not search.lower().endswith(" г"):
            ret = _do_search(f"{search} г")
            raw_items = list(list_items(ret))

        # KZ entries carry a null-GUID FIAS ("00000000-…"), not empty string.
        # Only skip when there is a real (non-null) FIAS.
        NULL_FIAS = "00000000-0000-0000-0000-000000000000"

        results = []
        for item in raw_items:
            f = fields_of(item)
            parent = f.get("ParentName", "")
            fias = f.get("FIAS", "")

            if country_code and country_code.upper() == "KZ":
                if fias and fias != NULL_FIAS:
                    continue

            raw_name = find_text(item, "Value")
            # Strip trailing " г" suffix so the client card shows a clean name.
            display_name = raw_name[:-2].rstrip() if raw_name.lower().endswith(" г") else raw_name

            results.append({
                "guid": find_text(item, "Key"),
                "name": display_name,
                "parent": parent,
                "type": f.get("Type", ""),
                "fias": fias,
                "iata": f.get("IATA", ""),
                "country": country_code or "",
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
        """Cancel an Order. Returns True on success.

        Per CSE Web API docs (DeleteDocuments, pages 230–233): parameters live
        inside a <m:List Key="parameters"> wrapper with <m:Properties> children
        for DocumentType/Number/Reason/ClientContact/Phone. DocumentType is
        "Order" or "Waybill"; SaveWaybillOffice yields an Order number.
        """
        inner = (
            self._auth(creds)
            + "<m:parameters>"
            + "<m:Key>parameters</m:Key>"
            + "<m:List>"
            + "<m:Key>parameters</m:Key>"
            + _prop("DocumentType", "Order")
            + _prop("Number", _esc(waybill_number))
            + _prop("Reason", _esc(reason))
            + _prop("ClientContact", _esc(contact))
            + _prop("Phone", _esc(phone))
            + "</m:List>"
            + "</m:parameters>"
        )
        try:
            ret = self._post("DeleteDocuments", inner, creds)
            # Response: <m:return><m:List><m:Properties>...</m:Properties>...
            # An Error=true Properties block signals failure.
            for list_item in list_items(ret):
                for prop in props_of(list_item):
                    key_el = prop.find(f"{_NM}Key")
                    val_el = prop.find(f"{_NM}Value")
                    if key_el is None or val_el is None:
                        continue
                    if (key_el.text or "").strip() == "Error":
                        if (val_el.text or "").strip().lower() in ("true", "1"):
                            return False
            return True
        except Exception as exc:
            logger.warning("CSE delete_document failed (waybill=%s): %s", waybill_number, exc)
            return False

    # ── GetFormsForDocuments ──────────────────────────────────────────────────

    def get_print_form(self, waybill_number: str, creds: dict) -> bytes:
        """Download PDF print form of an Order. Returns raw PDF bytes.

        Per CSE Web API docs (GetFormsForDocuments, pages 189–195):
          - <m:parameters> children are <m:List> (Key/Value/ValueType), NOT
            <m:Properties>. Using Properties here silently returns no BData.
          - DocumentType is "order" (the object SaveWaybillOffice produced) or
            "waybill" (an internal delivery leg). For customer print forms we
            want the Order document.
        """
        # <Name> pins the specific print form. Without it CSE returns whichever
        # form is set as default in the account settings — could change any day
        # to a "Марка ГМХ" (parcel label) or a variant. "Универсальная печатная
        # форма документа ЗАКАЗ" is the canonical customer-facing order print.
        inner = (
            self._auth(creds)
            + "<m:documents>"
            + "<m:Key>Documents</m:Key>"
            + f"<m:List><m:Key>{_esc(waybill_number)}</m:Key></m:List>"
            + "</m:documents>"
            + "<m:parameters>"
            + "<m:Key>Parameters</m:Key>"
            + "<m:List><m:Key>DocumentType</m:Key><m:Value>order</m:Value><m:ValueType>string</m:ValueType></m:List>"
            + "<m:List><m:Key>Type</m:Key><m:Value>print</m:Value><m:ValueType>string</m:ValueType></m:List>"
            + "<m:List><m:Key>Name</m:Key><m:Value>Универсальная печатная форма документа ЗАКАЗ</m:Value><m:ValueType>string</m:ValueType></m:List>"
            + "<m:List><m:Key>Format</m:Key><m:Value>pdf</m:Value><m:ValueType>string</m:ValueType></m:List>"
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
        """Get status event history for an Order.

        Per CSE Web API docs (Tracking method, page 137–145):
          - Request: DocumentType="Order" and OnlySelectedType=true, with the
            order number in <m:List><m:Key>{number}</m:Key></m:List>.
          - Response: each order's <m:List> contains metadata <m:Properties>
            children plus one <m:List> per status event. The event's <m:Key>
            holds the status name (Russian), and <m:Properties> children carry
            GUID / Comment / RecorderGUID / RecorderName / DateTime /
            DeliveryDateTime / Recipient.
          - A trailing <m:Tables Key="Waybills"> contains waybill-level events
            (delivery legs); we merge them into the same event list so the
            customer sees the full timeline.
        """
        inner = (
            self._auth(creds)
            + "<m:documents>"
            + "<m:Key>Documents</m:Key>"
            + "<m:Properties>"
            + "<m:Key>DocumentType</m:Key>"
            + "<m:Value>Order</m:Value>"
            + "<m:ValueType>string</m:ValueType>"
            + "</m:Properties>"
            + "<m:Properties>"
            + "<m:Key>OnlySelectedType</m:Key>"
            + "<m:Value>true</m:Value>"
            + "<m:ValueType>boolean</m:ValueType>"
            + "</m:Properties>"
            + f"<m:List><m:Key>{_esc(waybill_number)}</m:Key></m:List>"
            + "</m:documents>"
            + "<m:parameters><m:Key>Parameters</m:Key></m:parameters>"
        )
        ret = self._post("Tracking", inner, creds)

        events: list[dict] = []
        for doc_item in list_items(ret):
            # 1) Order-level events: direct <m:List> children of the document.
            for status_item in list_items(doc_item):
                events.extend(_tracking_events_from(status_item))

            # 2) Waybill-level events: inside <m:Tables Key="Waybills">/<m:List>.
            for tables_el in doc_item.findall(f"{_NM}Tables"):
                for waybill_item in list_items(tables_el):
                    for status_item in list_items(waybill_item):
                        events.extend(_tracking_events_from(status_item))

        # Sort by occurred_at ascending so caller sees chronological order.
        events.sort(key=lambda e: e.get("occurred_at", ""))
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

    def recalc_with_extras(
        self,
        from_geo: str,
        to_geo: str,
        weight: float,
        qty: int,
        creds: dict,
        *,
        urgency_guid: str,
        cargo_type_guid: str | None = None,
        volume_weight: float = 0.0,
        delivery_of_cargo: str = "",
        declared_value: float = 0.0,
        insurance_rate: float = 0.0,
        additional_service_guids: list[str] | None = None,
    ) -> dict | None:
        """Second-Calc for a specific urgency including add-on services.

        Used by the checkout flow: after the user picks Страхование / declared
        value / Самовывоз, we ask CSE for the fully-loaded final price so what
        the customer clicks "Pay" for matches CSE billing.

        Returns a single tariff dict for the requested urgency (or None if CSE
        returned no matching row).
        """
        if not cargo_type_guid:
            try:
                cargo_type_guid = self._cargo_type_guid(creds)
            except Exception as exc:
                logger.warning("CSE: cargo type GUID unavailable (%s)", exc)
                cargo_type_guid = ""
        inner = _build_calc_inner(
            self._login(creds), self._password(creds),
            from_geo, to_geo, weight, qty, cargo_type_guid,
            volume_weight,
            urgency_guid=urgency_guid,
            delivery_of_cargo=delivery_of_cargo,
            declared_value=declared_value,
            insurance_rate=insurance_rate,
            additional_service_guids=additional_service_guids,
        )
        ret = self._post("Calc", inner, creds, timeout=_CALC_TIMEOUT)
        tariffs = parse_calc_response(ret)
        # Even when Urgency is passed some installs still return every urgency;
        # explicitly pick the one requested.
        for t in tariffs:
            if t.get("urgency_guid") == urgency_guid:
                return t
        return tariffs[0] if tariffs else None

    # ── SaveWaybillOffice ─────────────────────────────────────────────────────

    def create_waybill(self, order_data: dict, creds: dict) -> str:
        """
        Create a waybill via SaveWaybillOffice. Returns the waybill number string.

        order_data keys:
            sender          — dict: full_name, phone, geography_guid (or city postcode), address
            recipient       — dict: full_name, phone, geography_guid (or city postcode), address,
                              urgency_guid (required by CSE)
            packages        — list of {weight_kg, quantity, description}
            take_date       — YYYY-MM-DD (defaults to today)
            declared_value  — float, объявленная стоимость
            cargo_type_guid — str, GUID типа груза (defaults to Груз)
            fragile / call_before_delivery / insurance — bool service flags → description
        """
        sender = order_data.get("sender", {})
        recipient = order_data.get("recipient", {})
        packages = order_data.get("packages", [])

        total_weight = sum(p.get("weight_kg", 0) * p.get("quantity", 1) for p in packages)
        total_qty = sum(p.get("quantity", 1) for p in packages)
        desc_parts = [p["description"] for p in packages if p.get("description")]

        # Handling markers that CSE has no dedicated Services GUID for —
        # kept in the free-form description so the courier sees them on the
        # printed label. Insurance / declared value are NOT listed here: they
        # are properly sent via <AdditionalServices> + Cargo amount fields.
        service_markers: list[str] = []
        if order_data.get("fragile"):
            service_markers.append("ХРУПКИЙ")
        if order_data.get("call_before_delivery"):
            service_markers.append("ПОЗВОНИТЬ ПЕРЕД ДОСТАВКОЙ")
        prefix = "; ".join(service_markers)
        body_desc = "; ".join(desc_parts) if desc_parts else "Посылка"
        description = f"{prefix}; {body_desc}" if prefix else body_desc

        take_date = order_data.get("take_date", date.today().isoformat())
        if "T" not in take_date:
            take_date += "T09:00:00"

        sender_geo = _esc(sender.get("geography_guid") or sender.get("city", ""))
        recipient_geo = _esc(recipient.get("geography_guid") or recipient.get("city", ""))
        sender_addr = _esc(sender.get("address") or sender.get("address_line1", ""))
        recipient_addr = _esc(recipient.get("address") or recipient.get("address_line1", ""))

        declared_value = order_data.get("declared_value", 0)
        cargo_type_guid = order_data.get("cargo_type_guid") or ""
        if not cargo_type_guid:
            try:
                cargo_type_guid = self._cargo_type_guid(creds)
            except Exception as exc:
                logger.warning("CSE: TypeOfCargo GUID unavailable for create_invoice (%s), sending empty", exc)
                cargo_type_guid = ""
        urgency_guid = _esc(recipient.get("urgency_guid", ""))
        if not urgency_guid:
            logger.warning(
                "CSE SaveWaybillOffice: urgency_guid missing for order_id=%s — "
                "CSE may reject the request. Ensure tariff engine passes urgency_guid.",
                order_data.get("order_id"),
            )

        login = _esc(self._login(creds))
        pwd = _esc(self._password(creds))

        # DeliveryType mapping. Internal enum → CSE's NameOfdeliverytype value
        # (see GetReferenceData:DeliveryType in CSE Web API docs).
        _DELIVERY_TYPE_MAP = {
            "door_to_door":           "ДоставкаДоДверей",
            "warehouse_to_door":      "СкладДверь",
            "door_to_warehouse":      "Самовывоз",
            "warehouse_to_warehouse": "СкладСклад",
        }
        delivery_type = order_data.get("delivery_type", "door_to_door")
        cse_delivery = _DELIVERY_TYPE_MAP.get(delivery_type, "ДоставкаДоДверей")

        # PVZ blocks. Per CSE SaveWaybillOffice docs the element is named
        # <PVZ> and lives INSIDE the <Sender> / <Recipient> blocks (after
        # Cargo for the recipient, at the end of Sender). "SenderPVZ" /
        # "RecipientPVZ" are silently dropped by the API. If PVZ is set,
        # CSE ignores the address/geography of that side.
        sender_pvz = _esc(sender.get("pvz_guid", ""))
        recipient_pvz = _esc(recipient.get("pvz_guid", ""))
        sender_pvz_xml = f"<m:PVZ>{sender_pvz}</m:PVZ>" if sender_pvz else ""
        recipient_pvz_xml = f"<m:PVZ>{recipient_pvz}</m:PVZ>" if recipient_pvz else ""

        declared_xml = ""
        if declared_value:
            declared_xml = (
                f"<m:DeclaredValueRate>{float(declared_value):.2f}</m:DeclaredValueRate>"
            )
            if order_data.get("insurance"):
                # CSE separates insurance value from declared value; both required for insurance
                declared_xml += (
                    f"<m:InsuranceRate>{float(declared_value):.2f}</m:InsuranceRate>"
                )
        comment_xml = (
            f"<m:Comment>{_esc(description)}</m:Comment>"
            if description else ""
        )
        urgency_xml = (
            f"<m:Urgency>{urgency_guid}</m:Urgency>"
            if urgency_guid else ""
        )

        # <AdditionalServices> at OrderData level. Страхование and
        # Объявленная стоимость are MUTUALLY EXCLUSIVE per CSE:
        #   error 05021: "Выбор услуги 'Страхование' не доступен совместно
        #                 с услугой 'Объявленная стоимость'."
        # When the customer picks insurance, insurance already implies the
        # declared value amount (sent via <DeclaredValueRate> in Cargo), and
        # we only bill for the insurance service. Otherwise (declared value
        # only) we bill the declared-value service alone.
        service_guids: list[str] = []
        if order_data.get("insurance"):
            service_guids.append(_CSE_SERVICE_GUIDS["insurance"])
        elif float(declared_value or 0) > 0:
            service_guids.append(_CSE_SERVICE_GUIDS["declared_value"])
        additional_services_xml = ""
        if service_guids:
            items = "".join(f"<m:Items>{_esc(g)}</m:Items>" for g in service_guids)
            additional_services_xml = f"<m:AdditionalServices>{items}</m:AdditionalServices>"

        # ── Dimensions + VolumeWeight ─────────────────────────────────────
        # CSE курьерская uses a 5000 divisor (from GetReferenceData:ShippingMethods
        # DimensionalWeightFactor). Volumetric weight in kg = L·W·H(cm) / 5000
        # per one piece; multiplied by the row's quantity for the aggregate.
        _VOL_DIVISOR = 5000.0
        first_pkg = packages[0] if packages else {}
        cargo_dims_xml = ""
        if first_pkg.get("width_cm") and first_pkg.get("height_cm") and first_pkg.get("depth_cm"):
            cargo_dims_xml = (
                f"<m:Length>{float(first_pkg.get('depth_cm', 0)):g}</m:Length>"
                f"<m:Width>{float(first_pkg.get('width_cm', 0)):g}</m:Width>"
                f"<m:Height>{float(first_pkg.get('height_cm', 0)):g}</m:Height>"
            )
        total_vol_weight = 0.0
        for p in packages:
            w = float(p.get("width_cm") or 0)
            h = float(p.get("height_cm") or 0)
            d = float(p.get("depth_cm") or 0)
            if w > 0 and h > 0 and d > 0:
                total_vol_weight += (w * h * d / _VOL_DIVISOR) * int(p.get("quantity", 1))
        vol_weight_xml = (
            f"<m:VolumeWeight>{round(total_vol_weight, 3)}</m:VolumeWeight>"
            if total_vol_weight > 0 else ""
        )

        # <CargoPackages> — one entry per package row (repeats for row.quantity>1
        # collapsed into a single element with PackageQty). Only emit when we
        # actually have per-row dimensions; otherwise Cargo aggregates suffice.
        cargo_packages_xml_parts: list[str] = []
        if len(packages) > 1 or (packages and cargo_dims_xml):
            for p in packages:
                w = float(p.get("width_cm") or 0)
                h = float(p.get("height_cm") or 0)
                d = float(p.get("depth_cm") or 0)
                if not (w > 0 and h > 0 and d > 0):
                    continue
                cargo_packages_xml_parts.append(
                    "<m:CargoPackages>"
                    f"<m:Length>{d:g}</m:Length>"
                    f"<m:Width>{w:g}</m:Width>"
                    f"<m:Height>{h:g}</m:Height>"
                    f"<m:Weight>{float(p.get('weight_kg', 0)):g}</m:Weight>"
                    f"<m:PackageQty>{int(p.get('quantity', 1))}</m:PackageQty>"
                    "</m:CargoPackages>"
                )
        cargo_packages_xml = "".join(cargo_packages_xml_parts)

        # ── Party-level extra fields (Official / EMail / Info) ────────────
        # Official = contact person: use company_name as Client when present,
        # then full_name becomes the contact (Official). Falls back to just
        # the full_name as Client when no company is set.
        def _party_client_official(party: dict) -> tuple[str, str]:
            company = (party.get("company") or "").strip()
            full = (party.get("full_name") or "").strip()
            if company:
                return company, full
            return full, ""

        s_client, s_official = _party_client_official(sender)
        r_client, r_official = _party_client_official(recipient)

        def _party_extras_xml(party: dict) -> str:
            xml = ""
            email = (party.get("email") or "").strip()
            info = (party.get("comment") or "").strip()
            if email:
                xml += f"<m:EMail>{_esc(email)}</m:EMail>"
            if info:
                xml += f"<m:Info>{_esc(info)}</m:Info>"
            return xml

        sender_official_xml = f"<m:Official>{_esc(s_official)}</m:Official>" if s_official else ""
        recipient_official_xml = f"<m:Official>{_esc(r_official)}</m:Official>" if r_official else ""

        # ── Notification channels for CSE (SMS + email to the sender) ─────
        reply_email = (sender.get("email") or "").strip()
        reply_phone = (sender.get("phone") or "").strip()
        reply_email_xml = f"<m:ReplyEMail>{_esc(reply_email)}</m:ReplyEMail>" if reply_email else ""
        reply_sms_xml = f"<m:ReplySMSPhone>{_esc(reply_phone)}</m:ReplySMSPhone>" if reply_phone else ""

        # <ClientNumber> = our internal order reference (max 20 chars per CSE
        # spec). CSE stores + echoes this back in ErrorInfo and its own UI,
        # giving us two-way traceability: their waybill number ↔ our order.id.
        client_number = _esc((order_data.get("order_reference") or "")[:20])

        # SaveWaybillOffice uses typed XML elements (not Element Key/Value/Fields).
        # TypeOfPayer: 0 = заказчик; WayOfPayment: 1 = безнал.
        inner = (
            f"<m:Language/>"
            f"<m:Login>{login}</m:Login>"
            f"<m:Password>{pwd}</m:Password>"
            f"<m:Company/>"
            f"<m:Number/>"
            f"<m:ClientNumber>{client_number}</m:ClientNumber>"
            f"<m:OrderData>"
            f"<m:Recipient>"
            f"<m:Client>{_esc(r_client)}</m:Client>"
            + recipient_official_xml +
            f"<m:Address>"
            f"<m:Geography>{recipient_geo}</m:Geography>"
            f"<m:Info>{recipient_addr}</m:Info>"
            f"<m:FreeForm>true</m:FreeForm>"
            f"</m:Address>"
            f"<m:Phone>{_esc(recipient.get('phone', ''))}</m:Phone>"
            + _party_extras_xml(recipient) +
            urgency_xml +
            f"<m:Cargo>"
            f"<m:CargoDescription>{_esc(body_desc)}</m:CargoDescription>"
            f"<m:CargoPackageQty>{int(total_qty)}</m:CargoPackageQty>"
            f"<m:Weight>{round(float(total_weight), 3)}</m:Weight>"
            + vol_weight_xml +
            cargo_dims_xml +
            declared_xml +
            cargo_packages_xml +
            f"</m:Cargo>"
            + recipient_pvz_xml +
            f"</m:Recipient>"
            f"<m:Sender>"
            f"<m:Client>{_esc(s_client)}</m:Client>"
            + sender_official_xml +
            f"<m:Address>"
            f"<m:Geography>{sender_geo}</m:Geography>"
            f"<m:Info>{sender_addr}</m:Info>"
            f"<m:FreeForm>true</m:FreeForm>"
            f"</m:Address>"
            f"<m:Phone>{_esc(sender.get('phone', ''))}</m:Phone>"
            + _party_extras_xml(sender) +
            sender_pvz_xml +
            f"</m:Sender>"
            + reply_email_xml +
            reply_sms_xml +
            f"<m:TakeDate>{_esc(take_date)}</m:TakeDate>"
            f"<m:TypeOfCargo>{_esc(cargo_type_guid)}</m:TypeOfCargo>"
            f"<m:TypeOfPayer>0</m:TypeOfPayer>"
            f"<m:WayOfPayment>1</m:WayOfPayment>"
            + comment_xml +
            f"<m:DeliveryOfCargo>{_esc(cse_delivery)}</m:DeliveryOfCargo>"
            + additional_services_xml +
            "</m:OrderData>"
            "<m:Office/>"
        )
        resp_xml = httpx.post(
            self._url(creds),
            content=build_envelope("SaveWaybillOffice", inner),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=_TIMEOUT,
        )
        resp_xml.raise_for_status()

        # Response: <m:return><m:Items><m:Value>waybill_number</m:Value><m:Error>false</m:Error>...
        try:
            root = ET.fromstring(resp_xml.text)
        except ET.ParseError as exc:
            raise RuntimeError(f"CSE SaveWaybillOffice: invalid XML response: {exc}") from exc

        ns = _NM
        body = root.find(f"{{{_NS_SOAP}}}Body")
        if body is None:
            raise RuntimeError("CSE SaveWaybillOffice: no SOAP Body in response")

        fault = body.find(f"{{{_NS_SOAP}}}Fault")
        if fault is not None:
            msg = (fault.findtext("faultstring") or "").strip()
            raise RuntimeError(f"CSE SaveWaybillOffice SOAP Fault: {msg}")

        ret_el = None
        for resp_el in body:
            ret_el = resp_el.find(f"{ns}return")
            if ret_el is not None:
                break

        if ret_el is None:
            raise RuntimeError("CSE SaveWaybillOffice: no <return> in response")

        # Check top-level error
        top_error = ret_el.find(f"{ns}Error")
        if top_error is not None and (top_error.text or "").strip().lower() == "true":
            error_info = (ret_el.findtext(f"{ns}ErrorInfo") or "").strip()
            raise RuntimeError(f"CSE SaveWaybillOffice error: {error_info or 'unknown'}")

        # Extract waybill number from Items/Value
        for items_el in ret_el.findall(f"{ns}Items"):
            item_error = items_el.find(f"{ns}Error")
            if item_error is not None and (item_error.text or "").strip().lower() == "true":
                error_info = (items_el.findtext(f"{ns}ErrorInfo") or "").strip()
                raise RuntimeError(f"CSE SaveWaybillOffice item error: {error_info or 'unknown'}")
            val_el = items_el.find(f"{ns}Value")
            if val_el is not None and (val_el.text or "").strip():
                return (val_el.text or "").strip()

        raise RuntimeError("CSE: SaveWaybillOffice returned no waybill number")

    # ── Service discovery ─────────────────────────────────────────────────────

    def get_available_services(
        self,
        creds: dict,
        from_city: str = "",
        to_city: str = "",
    ) -> list[CarrierServiceOption]:
        from app.modules.carriers.cse_geography import city_to_postcode_geo

        services: list[CarrierServiceOption] = [
            CarrierServiceOption(
                code="fragile",
                name="Хрупкий груз",
                available=True,
                note="Отмечается в описании вложения",
            ),
            # CSE Services reference GUIDs (used later when we migrate the dispatch
            # call to SaveDocuments/AdditionalServices):
            #   declared_value -> 6da21fe7-4f13-11dc-bda1-0015170f8c09
            #   insurance      -> cc03d9ad-61f4-11dc-bda1-0015170f8c09
            # Both are wired today via typed XML elements in SaveWaybillOffice:
            #   declared_value -> <m:DeclaredValueRate>
            #   insurance      -> <m:InsuranceRate>  (also requires declared value)
            CarrierServiceOption(
                code="declared_value",
                name="Объявленная стоимость",
                available=True,
                note="Задекларированная стоимость груза (лимит компенсации при потере)",
            ),
            CarrierServiceOption(
                code="insurance",
                name="Страхование",
                available=True,
                note="Требует указания объявленной стоимости; стоимость уточняется индивидуально",
            ),
            CarrierServiceOption(
                code="call_before_delivery",
                name="Звонок перед доставкой",
                available=True,
                note="Включено в тариф",
            ),
        ]

        cod_available = False
        card_available = False
        info_fetched = False

        if from_city and to_city:
            from_geo = city_to_postcode_geo(from_city)
            to_geo = city_to_postcode_geo(to_city)
            if from_geo and to_geo:
                try:
                    info = self.get_delivery_info(from_geo, to_geo, creds)
                    cod_available = bool(info.get("cod_available"))
                    card_available = bool(info.get("card_available"))
                    info_fetched = True
                except Exception as exc:
                    logger.debug("CSE get_delivery_info (non-fatal): %s", exc)

        note_suffix = "" if info_fetched else " (не удалось определить для маршрута)"
        services.append(CarrierServiceOption(
            code="cod",
            name="Наложенный платёж (COD)",
            available=cod_available,
            note=f"Доступность зависит от маршрута{note_suffix}",
        ))
        services.append(CarrierServiceOption(
            code="card_payment",
            name="Оплата картой при получении",
            available=card_available,
            note=f"Доступность зависит от маршрута{note_suffix}",
        ))
        return services

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
    volume_weight: float = 0.0,
    *,
    urgency_guid: str = "",
    delivery_of_cargo: str = "",
    declared_value: float = 0.0,
    insurance_rate: float = 0.0,
    additional_service_guids: list[str] | None = None,
) -> str:
    """Build the SOAP body for a CSE Calc request.

    volume_weight — volumetric weight in kg (CSE курьерская divisor = 5000, from
    ShippingMethods.DimensionalWeightFactor). Formula: sum((L·W·H(cm) / 5000) × qty).
    If > 0 we emit <VolumeWeight>; CSE bills by max(Weight, VolumeWeight).
    Omitting it underquotes bulky-light shipments.

    Optional (Phase 2 — recalc-after-services flow):
      urgency_guid            — scope the calc to a single tariff (else all 6).
      delivery_of_cargo       — CSE NameOfdeliverytype string ("ДоставкаДоДверей",
                                "Самовывоз", "СкладДверь", "СкладСклад").
      declared_value          — <DeclaredValueRate> amount.
      insurance_rate          — <InsuranceRate> amount (usually = declared_value).
      additional_service_guids — Services reference GUIDs to bill with the
                                shipment (Страхование, Объявленная стоимость, …).
                                Emitted via <Tables><Key>AdditionalServices</Key>.
    """
    vol_field = ""
    if volume_weight and volume_weight > 0:
        vol_field = (
            f"<m:Fields><m:Key>VolumeWeight</m:Key><m:Value>{volume_weight:.3f}</m:Value>"
            "<m:ValueType>float</m:ValueType></m:Fields>"
        )
    urgency_field = ""
    if urgency_guid:
        urgency_field = (
            f"<m:Fields><m:Key>Urgency</m:Key><m:Value>{_esc(urgency_guid)}</m:Value>"
            "<m:ValueType>string</m:ValueType></m:Fields>"
        )
    delivery_field = ""
    if delivery_of_cargo:
        delivery_field = (
            f"<m:Fields><m:Key>DeliveryType</m:Key><m:Value>{_esc(delivery_of_cargo)}</m:Value>"
            "<m:ValueType>string</m:ValueType></m:Fields>"
        )
    declared_field = ""
    if declared_value and declared_value > 0:
        declared_field = (
            f"<m:Fields><m:Key>DeclaredValueRate</m:Key><m:Value>{float(declared_value):.2f}</m:Value>"
            "<m:ValueType>float</m:ValueType></m:Fields>"
        )
    insurance_field = ""
    if insurance_rate and insurance_rate > 0:
        insurance_field = (
            f"<m:Fields><m:Key>InsuranceRate</m:Key><m:Value>{float(insurance_rate):.2f}</m:Value>"
            "<m:ValueType>float</m:ValueType></m:Fields>"
        )
    services_block = ""
    if additional_service_guids:
        items = "".join(
            f"<m:List><m:Key>Service</m:Key><m:Value>{_esc(g)}</m:Value>"
            "<m:ValueType>string</m:ValueType></m:List>"
            for g in additional_service_guids if g
        )
        if items:
            services_block = (
                "<m:Tables><m:Key>AdditionalServices</m:Key>"
                + items +
                "</m:Tables>"
            )
    return (
        f"<m:login>{_esc(login)}</m:login>"
        f"<m:password>{_esc(password)}</m:password>"
        "<m:data>"
        "<m:Key>Destinations</m:Key>"
        "<m:List>"
        "<m:Key>Destination</m:Key>"
        f"<m:Fields><m:Key>SenderGeography</m:Key><m:Value>{_esc(from_geo)}</m:Value>"
        "<m:ValueType>string</m:ValueType></m:Fields>"
        f"<m:Fields><m:Key>RecipientGeography</m:Key><m:Value>{_esc(to_geo)}</m:Value>"
        "<m:ValueType>string</m:ValueType></m:Fields>"
        f"<m:Fields><m:Key>TypeOfCargo</m:Key><m:Value>{_esc(cargo_type_guid)}</m:Value>"
        "<m:ValueType>string</m:ValueType></m:Fields>"
        f"<m:Fields><m:Key>Weight</m:Key><m:Value>{weight:.3f}</m:Value>"
        "<m:ValueType>float</m:ValueType></m:Fields>"
        + vol_field
        + urgency_field
        + delivery_field
        + declared_field
        + insurance_field +
        f"<m:Fields><m:Key>Qty</m:Key><m:Value>{qty}</m:Value>"
        "<m:ValueType>int</m:ValueType></m:Fields>"
        + services_block +
        "</m:List>"
        "</m:data>"
        "<m:parameters><m:Key>Parameters</m:Key></m:parameters>"
    )
