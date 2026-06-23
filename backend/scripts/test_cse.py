"""
Тест подключения к CSE API с тестовыми учётными данными.
Запуск: python -m scripts.test_cse
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import httpx
from app.modules.carriers.api_clients.cse import (
    CSEAPIClient,
    build_envelope,
    extract_return,
    list_items,
    find_text,
    fields_of,
    _build_calc_inner,
    DEFAULT_API_URL,
)
from app.modules.carriers.cse_geography import city_to_postcode_geo

CREDS = {
    "login": "test",
    "password": "2016",
    "api_url": DEFAULT_API_URL,
}

client = CSEAPIClient()


def raw_request(method: str, inner: str) -> tuple[int, str]:
    envelope = build_envelope(method, inner)
    resp = httpx.post(
        DEFAULT_API_URL,
        content=envelope,
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=20,
    )
    return resp.status_code, resp.text


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("="*60)


def test_ping():
    section("0. Ping (no auth required)")
    status, body = raw_request("Ping", "")
    print(f"HTTP {status}")
    print(body[:500])
    return status == 200 and "true" in body.lower()


def test_raw_soap():
    section("1. RAW SOAP — GetReferenceData TypesOfCargo (correct format)")
    inner = (
        "<m:login>test</m:login>"
        "<m:password>2016</m:password>"
        "<m:parameters><m:Key>TypesOfCargo</m:Key></m:parameters>"
    )
    status, body = raw_request("GetReferenceData", inner)
    print(f"HTTP {status}")
    print(body[:1500])
    return status == 200


def test_connection():
    section("2. test_connection()")
    try:
        ok = client.test_connection(CREDS)
        print("PASS:", ok)
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


def test_geography():
    section("3. GetReferenceData → Geography (search=Алматы)")
    try:
        results = client.search_geography("Алматы", CREDS)
        print(f"Results: {len(results)}")
        for r in results[:5]:
            print(f"  GUID={r['guid']}  name={r['name']}  parent={r['parent']}")
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


def test_calc():
    section("4. Calc — Алматы → Астана, 2.5 kg")
    from_geo = city_to_postcode_geo("алматы")
    to_geo   = city_to_postcode_geo("астана")
    print(f"from_geo={from_geo}  to_geo={to_geo}")
    try:
        tariffs = client.calc(from_geo, to_geo, 2.5, 1, CREDS)
        print(f"Tariffs returned: {len(tariffs)}")
        for t in tariffs:
            print(f"  {t['service_name']:30}  {t['price']:>10.2f} {t['currency']}  "
                  f"{t['min_days']}-{t['max_days']} дн.")
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


def test_pvz():
    section("5. GetReferenceData → pvz (first 3)")
    try:
        points = client.get_pvz(CREDS)
        print(f"PVZ total: {len(points)}")
        for p in points[:3]:
            print(f"  {p['guid']}  {p['address']}  {p['city']}")
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


def test_delivery_dates():
    section("6. GetReferenceData → availabledeliverydates")
    from_geo = city_to_postcode_geo("алматы")
    to_geo   = city_to_postcode_geo("астана")
    try:
        dates = client.get_available_delivery_dates(from_geo, to_geo, CREDS)
        print(f"Available dates: {len(dates)}")
        for d in dates[:3]:
            print(f"  {d['date']}  slots={len(d.get('slots', []))}  "
                  f"from={d.get('time_from')} to={d.get('time_to')}")
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


def test_take_dates():
    section("7. GetReferenceData → availabletakedates")
    from_geo = city_to_postcode_geo("алматы")
    try:
        dates = client.get_available_take_dates(from_geo, CREDS)
        print(f"Available take dates: {len(dates)}")
        for d in dates[:3]:
            print(f"  {d['date']}  slots={len(d.get('slots', []))}")
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


def test_delivery_info():
    section("8. GetReferenceData → deliveryinfo")
    from_geo = city_to_postcode_geo("алматы")
    to_geo   = city_to_postcode_geo("астана")
    try:
        info = client.get_delivery_info(from_geo, to_geo, CREDS)
        print(f"min_days={info['min_days']}  max_days={info['max_days']}")
        print(f"COD={info['cod_available']}  card={info['card_available']}")
        print(f"Services: {len(info['services'])}")
        return True
    except Exception as e:
        print("FAIL:", e)
        return False


if __name__ == "__main__":
    print("CSE API Connection Test")
    print(f"Endpoint: {DEFAULT_API_URL}")
    print(f"Login: {CREDS['login']}")

    ping_ok = test_ping()
    raw_ok = test_raw_soap()

    if not ping_ok:
        print("\n[!] Ping failed — endpoint unreachable or wrong namespace")
    elif not raw_ok:
        print("\n[!] Raw SOAP format error (check namespace/structure)")

    results = {
        "ping":                 ping_ok,
        "test_connection":      test_connection(),
        "geography":            test_geography(),
        "calc":                 test_calc(),
        "pvz":                  test_pvz(),
        "delivery_dates":       test_delivery_dates(),
        "take_dates":           test_take_dates(),
        "delivery_info":        test_delivery_info(),
    }

    section("SUMMARY")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
