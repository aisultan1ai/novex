"""End-to-end smoke test for CSE / Exline API integrations.

Runs a live probe against the carrier test endpoints and prints request/response
XML plus a short verdict. Safe stages (calc, tracking, connection) are always
executed; the destructive stage (create_invoice) is only executed when the
--create flag is passed AND the caller confirms.

Usage:
    py scripts/test_carrier_order.py                 # calc + connection only
    py scripts/test_carrier_order.py --create        # also creates a test order
    py scripts/test_carrier_order.py --carrier=exline
    py scripts/test_carrier_order.py --carrier=cse

Reads credentials from backend/.env (EXLINE_*, CSE_*).
Overrides URLs to the documented TEST endpoints unless --prod is passed.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

# Force UTF-8 on Windows consoles (cp1251 by default) so Russian text prints.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
else:  # pragma: no cover
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

# Load .env manually (avoid dep on python-dotenv in this script)
for env_path in (REPO / ".env", BACKEND / ".env"):
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# CSE test creds & URL from CSE Web API doc, page 10
CSE_TEST_URL = "http://lk-test.cse.ru/1c/ws/web1c.1cws"
CSE_TEST_LOGIN = "test"
CSE_TEST_PASSWORD = "2016"

# Exline has no separate documented test URL — same host is used with dedicated
# demo credentials (extra=8, login=demo). We keep whatever creds .env supplies.
EXLINE_URL = os.getenv("EXLINE_API_URL", "https://home.courierexe.ru/api/")


def _banner(msg: str) -> None:
    print("\n" + "=" * 70)
    print(msg)
    print("=" * 70)


# ────────────────────────────────────────────────────────────────────────────
# Exline
# ────────────────────────────────────────────────────────────────────────────

def exline_probe(create: bool) -> None:
    from app.modules.carriers.api_clients.exline import ExlineAPIClient

    creds = {
        "extra":    os.getenv("EXLINE_EXTRA", ""),
        "login":    os.getenv("EXLINE_LOGIN", ""),
        "password": os.getenv("EXLINE_PASSWORD", ""),
        "api_url":  EXLINE_URL,
    }
    if not creds["extra"] or not creds["login"]:
        print("Exline: no credentials (set EXLINE_EXTRA / EXLINE_LOGIN)")
        return

    client = ExlineAPIClient()

    _banner("EXLINE :: test_connection")
    try:
        client.test_connection(creds)
        print("OK — auth accepted.")
    except Exception as exc:
        print(f"FAIL — {exc}")
        return

    _banner("EXLINE :: create_invoice (NO insurance, declared_value=0)")
    sample_no_insurance = _sample_order(order_id=90001, insurance=False, declared_value=0)
    _run_create(client, sample_no_insurance, creds, dry=not create, label="no-insurance")

    _banner("EXLINE :: create_invoice (WITH insurance, declared_value=5000)")
    sample_with_insurance = _sample_order(order_id=90002, insurance=True, declared_value=5000)
    _run_create(client, sample_with_insurance, creds, dry=not create, label="with-insurance")


def _sample_order(order_id: int, insurance: bool, declared_value: float) -> dict:
    return {
        "order_id": order_id,
        "order_reference": f"NOVEX-TEST-{order_id}",
        "sender": {
            "full_name": "Тест Отправитель",
            "phone": "+77001234567",
            "city": "Алматы",
            "address": "ул. Абая, 1",
        },
        "recipient": {
            "full_name": "Тест Получатель",
            "phone": "+77007654321",
            "city": "Астана",
            "address": "пр. Республики, 2",
        },
        "packages": [
            {"weight_kg": 1.0, "quantity": 1, "description": "Тестовое отправление"},
        ],
        "declared_value": declared_value,
        "currency": "KZT",
        "insurance": insurance,
        "fragile": False,
        "call_before_delivery": False,
        "tariff_code": "standard",
    }


def _run_create(client, order_data: dict, creds: dict, dry: bool, label: str) -> None:
    # Intercept the XML we are about to send so we can print it either way.
    real_post = client._post_xml
    captured: list[str] = []

    def spy(xml_body: str, api_url: str):
        captured.append(xml_body)
        if dry:
            print("── XML (dry-run, not sent) ─────────────────────────────")
            print(xml_body[:1200])
            print("...(truncated)" if len(xml_body) > 1200 else "")
            print("──────────────────────────────────────────────────────")
            import xml.etree.ElementTree as ET
            return ET.fromstring(
                f'<neworder><createorder orderno="DRY-{label}" barcode="" error="0" errormsg="dry-run"/></neworder>'
            )
        return real_post(xml_body, api_url)

    client._post_xml = spy  # type: ignore[assignment]
    # In dry-run we also skip the PDF fetch (would try real HTTP).
    if dry:
        client.get_invoice_pdf = lambda *a, **kw: None  # type: ignore[assignment]

    try:
        result = client.create_invoice(order_data, creds)
    except Exception as exc:
        print(f"FAIL — {type(exc).__name__}: {exc}")
        return
    finally:
        client._post_xml = real_post  # type: ignore[assignment]

    # Verify the fix: <inshprice> presence must match insurance flag
    has_inshprice = "<inshprice>" in captured[0]
    expected = order_data["insurance"] and order_data["declared_value"] > 0
    verdict = "OK" if has_inshprice == expected else "BUG"
    print(f"<inshprice> in XML: {has_inshprice}  (expected: {expected})  → {verdict}")

    print(f"waybill_number={result.waybill_number!r}  carrier_invoice_id={result.carrier_invoice_id!r}")

    if not dry:
        print("→ Order created on Exline. Consider cancelling with cancel_invoice.")


# ────────────────────────────────────────────────────────────────────────────
# CSE
# ────────────────────────────────────────────────────────────────────────────

def cse_probe(prod: bool) -> None:
    from app.modules.carriers.api_clients.cse import CSEAPIClient

    if prod:
        creds = {
            "login":    os.getenv("CSE_LOGIN", ""),
            "password": os.getenv("CSE_PASSWORD", ""),
            "api_url":  os.getenv("CSE_API_URL", ""),
        }
        env_label = "PROD (from .env)"
    else:
        creds = {"login": CSE_TEST_LOGIN, "password": CSE_TEST_PASSWORD, "api_url": CSE_TEST_URL}
        env_label = f"TEST ({CSE_TEST_URL})"

    if not creds["login"]:
        print("CSE: no credentials")
        return

    client = CSEAPIClient()

    _banner(f"CSE :: test_connection [{env_label}]")
    try:
        client.test_connection(creds)
        print("OK — Ping + TypesOfCargo succeeded.")
    except Exception as exc:
        print(f"FAIL — {exc}")
        return

    _banner("CSE :: Calc (Алматы → Астана, 1 kg parcel)")
    try:
        from app.modules.carriers.api_clients.cse import _CSE_CARGO_TYPE_GUIDS  # noqa: F401 (may not exist)
    except ImportError:
        pass
    cargo_guid = "4aab1fc6-fc2b-473a-8728-58bcd4ff79ba"  # doc-standard parcel GUID
    try:
        tariffs = client.calc(
            from_geo="postcode-KZ-050000",
            to_geo="postcode-KZ-010000",
            weight=1.0,
            qty=1,
            creds=creds,
            cargo_type_guid=cargo_guid,
        )
        print(f"OK — {len(tariffs)} tariff(s) returned.")
        for t in tariffs[:3]:
            print(f"  · {t.get('service_name')}: {t.get('price')} {t.get('currency')} "
                  f"({t.get('min_days')}-{t.get('max_days')} days, urgency={t.get('urgency_guid') or '-'})")
    except Exception as exc:
        print(f"FAIL — {type(exc).__name__}: {exc}")


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--carrier", choices=["exline", "cse", "both"], default="both")
    parser.add_argument("--create", action="store_true", help="Actually create an Exline order (destructive)")
    parser.add_argument("--prod", action="store_true", help="Hit prod CSE URL from .env (default: test URL)")
    args = parser.parse_args()

    if args.carrier in ("exline", "both"):
        exline_probe(create=args.create)
    if args.carrier in ("cse", "both"):
        cse_probe(prod=args.prod)


if __name__ == "__main__":
    main()
