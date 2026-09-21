"""P3-1: COD amount is folded into Calc request so the returned price
reflects the CSE agent fee."""
from __future__ import annotations

from unittest.mock import patch

from app.modules.carriers.api_clients.cse import CSEAPIClient, _build_calc_inner


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def _calc_ok_envelope(price: float = 1234.56) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:m="http://www.cargo3.ru">'
        '<soap:Body><m:CalcResponse><m:return>'
        '<m:List>'  # Destination
        '<m:List>'  # Tariff
        '<m:Value>tariff-guid-1</m:Value>'
        f'<m:Fields><m:Key>Total</m:Key><m:Value>{price}</m:Value>'
        '<m:ValueType>float</m:ValueType></m:Fields>'
        '<m:Fields><m:Key>Urgency</m:Key><m:Value>urg-1</m:Value>'
        '<m:ValueType>string</m:ValueType></m:Fields>'
        '<m:Fields><m:Key>UrgencyName</m:Key><m:Value>Стандарт</m:Value>'
        '<m:ValueType>string</m:ValueType></m:Fields>'
        '<m:Fields><m:Key>CurrencyName</m:Key><m:Value>KZT</m:Value>'
        '<m:ValueType>string</m:ValueType></m:Fields>'
        '<m:Fields><m:Key>MinPeriod</m:Key><m:Value>3</m:Value>'
        '<m:ValueType>int</m:ValueType></m:Fields>'
        '<m:Fields><m:Key>MaxPeriod</m:Key><m:Value>5</m:Value>'
        '<m:ValueType>int</m:ValueType></m:Fields>'
        '</m:List>'
        '</m:List>'
        '</m:return></m:CalcResponse></soap:Body>'
        '</soap:Envelope>'
    )


class TestBuildCalcInnerWithCod:
    def test_no_cod_leaves_fields_absent(self):
        inner = _build_calc_inner(
            "u", "p", "KZ-050000", "KZ-010000",
            weight=1.0, qty=1, cargo_type_guid="ct",
        )
        assert "<m:Key>AmountCOD</m:Key>" not in inner
        assert "<m:Key>PaymentByRecipient</m:Key>" not in inner

    def test_kzt_cod_emits_all_three_fields(self):
        inner = _build_calc_inner(
            "u", "p", "KZ-050000", "KZ-010000",
            weight=1.0, qty=1, cargo_type_guid="ct",
            cod_amount=15000, cod_currency="KZT",
        )
        assert "<m:Key>AmountCOD</m:Key>" in inner
        assert "<m:Value>15000.00</m:Value>" in inner
        assert "<m:Key>CurrencyCOD</m:Key>" in inner
        # KZT currency GUID from the shared mapping.
        assert "<m:Value>d3a2419e-e7e9-11e8-80c1-7cd30aec6901</m:Value>" in inner
        assert "<m:Key>PaymentByRecipient</m:Key>" in inner

    def test_zero_amount_no_cod(self):
        inner = _build_calc_inner(
            "u", "p", "KZ-050000", "KZ-010000",
            weight=1.0, qty=1, cargo_type_guid="ct",
            cod_amount=0,
        )
        assert "<m:Key>AmountCOD</m:Key>" not in inner

    def test_unknown_currency_silently_skipped(self):
        # We already validate currencies at the API boundary (create_waybill);
        # here the Calc helper just drops COD fields rather than raise, so
        # a bad currency doesn't nuke the whole quote.
        inner = _build_calc_inner(
            "u", "p", "KZ-050000", "KZ-010000",
            weight=1.0, qty=1, cargo_type_guid="ct",
            cod_amount=100, cod_currency="XYZ",
        )
        assert "<m:Key>AmountCOD</m:Key>" not in inner


class TestRecalcWithExtrasCod:
    def test_recalc_passes_cod_downstream(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_calc_ok_envelope())

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            tariff = client.recalc_with_extras(
                "KZ-050000", "KZ-010000",
                weight=1.0, qty=1,
                creds={"api_url": "http://x", "login": "u", "password": "p"},
                urgency_guid="urg-1",
                cargo_type_guid="ct",
                cod_amount=25000, cod_currency="KZT",
            )
        assert tariff is not None
        assert tariff["price"] == 1234.56

        body = captured["body"].decode()
        assert "<m:Value>25000.00</m:Value>" in body
        assert "<m:Key>PaymentByRecipient</m:Key>" in body
