# -*- coding: utf-8 -*-
"""
Получает список городов Exline через API справочник (townlist).
Если справочник пустой — тестирует каждый город через калькулятор.

Запуск:
  cd backend
  EXLINE_EXTRA=447 EXLINE_LOGIN=test EXLINE_PASSWORD=test123 python scripts/check_exline_cities.py
"""

import os
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

import httpx

# Принудительно UTF-8 для Windows-терминала
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EXTRA    = os.getenv("EXLINE_EXTRA", "")
LOGIN    = os.getenv("EXLINE_LOGIN", "")
PASSWORD = os.getenv("EXLINE_PASSWORD", "")
API_URL  = os.getenv("EXLINE_API_URL", "https://home.courierexe.ru/api/")
TIMEOUT  = 15


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _auth() -> str:
    return f'<auth extra="{_esc(EXTRA)}" login="{_esc(LOGIN)}" pass="{_esc(PASSWORD)}"/>'


def _post(xml: str) -> ET.Element:
    resp = httpx.post(
        API_URL,
        content=xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return ET.fromstring(resp.text)


# -- Sposob 1: spravochnik gorodov (townlist) ---------------------------------

def fetch_townlist() -> list[dict]:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><townlist>{_auth()}</townlist>'
    root = _post(xml)

    if root.attrib.get("error") == "1":
        print("[!] Oshibka avtorizatsii (townlist)")
        return []

    cities = []
    for town in root.iter("town"):
        name = (
            town.attrib.get("name")
            or (town.find("name").text if town.find("name") is not None else "")
            or ""
        ).strip()
        if name:
            cities.append({
                "name":   name,
                "code":   town.attrib.get("code", ""),
                "region": town.attrib.get("region", ""),
                "type":   town.attrib.get("type", ""),
            })
    return cities


# -- Sposob 2: test cherez kalkulator -----------------------------------------

OUR_CITIES = [
    "Алматы", "Астана", "Шымкент", "Актобе", "Атырау", "Актау",
    "Кокшетау", "Костанай", "Кызылорда", "Оскемен", "Павлодар",
    "Петропавловск", "Семей", "Талдыкорган", "Тараз", "Уральск",
    "Жезказган", "Караганда",
    "Темиртау", "Экибастуз", "Рудный", "Степногорск", "Капшагай",
    "Туркестан", "Балхаш", "Талгар", "Каскелен", "Аксай",
    "Жанаозен", "Риддер", "Жаркент",
    "Кульсары", "Лисаковск", "Аркалык", "Саран", "Шахтинск",
    "Сарыагаш", "Арыс", "Кентау", "Жанакорган", "Абай",
    "Приозёрск", "Щучинск", "Бурабай", "Аксу", "Есик", "Текели",
]


def check_via_calculator(city: str) -> tuple[bool, str]:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<calculator>"
        f"{_auth()}"
        "<order>"
        "<pricetype>CUSTOMER</pricetype>"
        "<sender><town>Алматы</town></sender>"
        f"<receiver><town>{_esc(city)}</town></receiver>"
        "<weight>2.000</weight>"
        "<service>2</service>"
        "<paytype>NO</paytype>"
        "</order>"
        "</calculator>"
    )
    root = _post(xml)
    if root.attrib.get("error") == "1":
        return False, "oshibka avtorizatsii"
    calc = root.find("calc")
    if calc is None:
        return False, "net pokrytiya"
    price_el = calc.find("price")
    if price_el is None or not (price_el.text or "").strip():
        return False, "pustaya tsena"
    try:
        price = Decimal(price_el.text.strip())
        return True, f"{price:,.0f} KZT"
    except InvalidOperation:
        return False, f"nekorrektno: {price_el.text!r}"


# -- Main ---------------------------------------------------------------------

def main() -> None:
    if not EXTRA or not LOGIN:
        print("[!] Ne zadany EXLINE_EXTRA / EXLINE_LOGIN")
        print("    Pример: EXLINE_EXTRA=447 EXLINE_LOGIN=test EXLINE_PASSWORD=test123 python scripts/check_exline_cities.py")
        sys.exit(1)

    print(f"Zapros spravoчnika gorodov (townlist)...\n")
    try:
        cities = fetch_townlist()
    except Exception as e:
        print(f"[!] Spravochnik nedostupen: {e}")
        cities = []

    if cities:
        print(f"Spravochnik vernul {len(cities)} gorodov:\n")
        for c in sorted(cities, key=lambda x: x["name"]):
            region = f"  [{c['region']}]" if c.get("region") else ""
            code   = f"  (kod: {c['code']})" if c.get("code") else ""
            print(f"  + {c['name']}{region}{code}")
        return

    # Spravochnik pust — testiruyem calculator
    print("[!] Spravochnik pust — testiruyu cherez calculator (Almaty → gorod, 2kg, Standart)\n")
    ok, fail = [], []
    for city in OUR_CITIES:
        if city == "Алматы":
            continue
        try:
            available, info = check_via_calculator(city)
        except Exception as e:
            available, info = False, str(e)
        mark = "[OK]" if available else "[--]"
        print(f"  {mark}  {city:<22} {info}")
        (ok if available else fail).append(city)

    print(f"\n{'─'*50}")
    print(f"Pokryto Exline: {len(ok)} gorodov")
    print(f"Net pokrytiya:  {len(fail)} gorodov")
    if fail:
        print("\nGoroda BEZ pokrytiya:")
        for c in fail:
            print(f"  - {c}")


if __name__ == "__main__":
    main()
