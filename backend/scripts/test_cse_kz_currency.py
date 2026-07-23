"""
Тест CSE API с KZ городами — проверяем что возвращается в поле Currency/CurrencyName.
Запуск: python -m scripts.test_cse_kz_currency
"""
from __future__ import annotations

import os
import sys
import logging
import xml.etree.ElementTree as ET
import warnings

warnings.filterwarnings("ignore")

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

import httpx

# Добавляем backend в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.carriers.api_clients.cse import (
    CSEAPIClient,
    build_envelope,
    extract_return,
    list_items,
    fields_of,
    find_text,
    _CSE_CURRENCY_GUID_TO_ISO,
    _CSE_CURRENCY_NAME_NORMALISE,
    DEFAULT_API_URL,
    TEST_API_URL,
)

# ─── Настройки подключения ────────────────────────────────────────────────────
LOGIN    = os.getenv("CSE_LOGIN",    "test")
PASSWORD = os.getenv("CSE_PASSWORD", "2016")
API_URL  = os.getenv("CSE_API_URL",  DEFAULT_API_URL)

CREDS = {"login": LOGIN, "password": PASSWORD, "api_url": API_URL}

# ─── KZ маршруты для теста ───────────────────────────────────────────────────
KZ_ROUTES = [
    ("postcode-KZ-050000", "postcode-KZ-010000", "Алматы → Астана"),
    ("postcode-KZ-010000", "postcode-KZ-050000", "Астана → Алматы"),
    ("postcode-KZ-050000", "postcode-KZ-160000", "Алматы → Шымкент"),
    ("postcode-KZ-010000", "postcode-KZ-030000", "Астана → Актобе"),
]

client = CSEAPIClient()


def section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print("=" * 70)


def raw_calc(from_geo: str, to_geo: str, weight: float = 1.0) -> str:
    """Возвращает сырой XML ответа Calc."""
    _NS_M = "http://www.cargo3.ru"
    inner = (
        f"<m:login>{LOGIN}</m:login>"
        f"<m:password>{PASSWORD}</m:password>"
        "<m:data>"
        "<m:Key>Destinations</m:Key>"
        "<m:List>"
        "<m:Key>Destination</m:Key>"
        f"<m:Fields><m:Key>SenderGeography</m:Key><m:Value>{from_geo}</m:Value>"
        "<m:ValueType>string</m:ValueType></m:Fields>"
        f"<m:Fields><m:Key>RecipientGeography</m:Key><m:Value>{to_geo}</m:Value>"
        "<m:ValueType>string</m:ValueType></m:Fields>"
        f"<m:Fields><m:Key>Weight</m:Key><m:Value>{weight}</m:Value>"
        "<m:ValueType>float</m:ValueType></m:Fields>"
        "<m:Fields><m:Key>Qty</m:Key><m:Value>1</m:Value>"
        "<m:ValueType>int</m:ValueType></m:Fields>"
        "</m:List>"
        "</m:data>"
        "<m:parameters><m:Key>Parameters</m:Key></m:parameters>"
    )
    resp = httpx.post(
        API_URL,
        content=build_envelope("Calc", inner),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.text


def parse_and_show_currencies(xml_text: str, label: str) -> None:
    """Парсит Calc ответ и выводит все поля Currency/CurrencyName."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")
        print(f"  Raw (first 500): {xml_text[:500]}")
        return

    _NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
    _NM = f"{{{_NS_M}}}" if (
        (_NS_M := "http://www.cargo3.ru") or True
    ) else ""
    _NM = "{http://www.cargo3.ru}"

    body = root.find(f"{{http://schemas.xmlsoap.org/soap/envelope/}}Body")
    if body is None:
        body = root.find(f"{{http://www.w3.org/2003/05/soap-envelope}}Body")
    if body is None:
        print("  No SOAP Body found")
        print(f"  Raw (first 800):\n{xml_text[:800]}")
        return

    # Check for SOAP Fault
    fault = body.find("{http://schemas.xmlsoap.org/soap/envelope/}Fault")
    if fault is None:
        fault = body.find("{http://www.w3.org/2003/05/soap-envelope}Fault")
    if fault is not None:
        msg = fault.findtext("faultstring") or ET.tostring(fault, encoding="unicode")
        print(f"  SOAP Fault: {msg}")
        return

    # Find CalcResponse
    calc_resp = body.find(f"{_NM}CalcResponse")
    if calc_resp is None:
        print(f"  No CalcResponse in body")
        print(f"  Body children: {[el.tag for el in body]}")
        return

    ret_el = calc_resp.find(f"{_NM}return")
    if ret_el is None:
        print("  No <return> in CalcResponse")
        return

    # Check for app-level error
    for prop in ret_el.findall(f"{_NM}Properties"):
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
                print(f"  API Error: {desc or 'unknown'}")
                return

    # Итерируем по тарифам
    tariff_count = 0
    for dest_item in ret_el.findall(f"{_NM}List"):
        for tariff_item in dest_item.findall(f"{_NM}List"):
            f = fields_of(tariff_item)

            if f.get("AdditionalService") is True:
                continue

            tariff_guid_raw = find_text(tariff_item, "Value")
            total = f.get("Total") or f.get("Price")
            urgency_name = f.get("UrgencyName") or f.get("Service") or "?"
            currency_name_raw = (f.get("CurrencyName") or "").strip()
            currency_guid_raw = (f.get("Currency") or "").strip()

            # Наша нормализация
            if currency_name_raw:
                currency_resolved = _CSE_CURRENCY_NAME_NORMALISE.get(currency_name_raw, currency_name_raw)
            else:
                currency_resolved = _CSE_CURRENCY_GUID_TO_ISO.get(currency_guid_raw, "??")

            tariff_count += 1
            print(
                f"  [{tariff_count}] {urgency_name[:35]:35s} "
                f"| total={total!s:10} "
                f"| CurrencyName={currency_name_raw!r:8} "
                f"| Currency(GUID)={currency_guid_raw[:8] if currency_guid_raw else 'N/A':8}... "
                f"| → resolved={currency_resolved}"
            )

    if tariff_count == 0:
        print("  Нет тарифов в ответе (0 строк). Маршрут недоступен?")
        # Показываем сырой ответ
        print(f"  Raw response (first 1200):\n{xml_text[:1200]}")


def test_currencies_reference() -> None:
    """Проверяем что CSE возвращает в GetReferenceData:Currencies."""
    section("GetReferenceData:Currencies — что реально возвращает API")
    _NS_M = "{http://www.cargo3.ru}"
    inner = (
        f"<m:login>{LOGIN}</m:login>"
        f"<m:password>{PASSWORD}</m:password>"
        "<m:parameters>"
        "<m:Key>parameters</m:Key>"
        "<m:List>"
        "<m:Key>Reference</m:Key>"
        "<m:Value>Currencies</m:Value>"
        "<m:ValueType>string</m:ValueType>"
        "</m:List>"
        "</m:parameters>"
    )
    try:
        resp = httpx.post(
            API_URL,
            content=build_envelope("GetReferenceData", inner),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=15,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        body = root.find("{http://schemas.xmlsoap.org/soap/envelope/}Body")
        if body is None:
            body = root.find("{http://www.w3.org/2003/05/soap-envelope}Body")
        gr = body.find(f"{_NS_M}GetReferenceDataResponse")
        ret = gr.find(f"{_NS_M}return")
        for item in ret.findall(f"{_NS_M}List"):
            key = item.findtext(f"{_NS_M}Key") or ""
            val = item.findtext(f"{_NS_M}Value") or ""
            f = fields_of(item)
            is_default = f.get("Default", False)
            full_name = f.get("FullName", "")
            print(f"  GUID={key[:36]}  Value={val!r:6}  FullName={full_name!r:20}  Default={is_default}")
    except Exception as e:
        print(f"  FAIL: {e}")


def test_kz_calc_routes() -> None:
    """Тестируем расчёт для KZ маршрутов."""
    for from_geo, to_geo, label in KZ_ROUTES:
        section(f"Calc: {label}  ({from_geo} → {to_geo})")
        print(f"  Endpoint: {API_URL}")
        print(f"  Login:    {LOGIN}")
        try:
            xml_text = raw_calc(from_geo, to_geo, weight=1.5)
            parse_and_show_currencies(xml_text, label)
        except httpx.HTTPStatusError as e:
            print(f"  HTTP Error {e.response.status_code}: {e.response.text[:300]}")
        except Exception as e:
            print(f"  Exception: {type(e).__name__}: {e}")


def test_via_client() -> None:
    """Тестируем через стандартный CSEAPIClient.calc()."""
    section("CSEAPIClient.calc() — через наш клиент (с нормализацией)")
    from_geo = "postcode-KZ-050000"
    to_geo   = "postcode-KZ-010000"
    print(f"  {from_geo} → {to_geo}  (Алматы → Астана)")
    try:
        tariffs = client.calc(from_geo, to_geo, 1.5, 1, CREDS)
        if not tariffs:
            print("  Нет тарифов")
        for t in tariffs:
            print(
                f"  {t['service_name'][:35]:35s} | "
                f"price={t['price']:8.2f} | currency={t['currency']}"
            )
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("CSE KZ Currency Test")
    print(f"Endpoint : {API_URL}")
    print(f"Login    : {LOGIN}")

    test_currencies_reference()
    test_kz_calc_routes()
    test_via_client()

    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70)
