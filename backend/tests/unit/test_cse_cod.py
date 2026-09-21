"""P1-3: COD support in SaveWaybillOffice.

Verifies that when order_data['cod'] is set:
  * TypeOfPayer becomes 1 (получатель), WayOfPayment maps by payment_method;
  * <AmountCOD>, <CurrencyCOD>, <PaymentByRecipient> are emitted inside <Cargo>;
  * unsupported currency raises before an API call.

Without cod, request must be unchanged from the legacy code path.
"""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from app.modules.carriers.api_clients.cse import CSEAPIClient


def _order_data(**overrides) -> dict:
    base = {
        "order_id": 42,
        "sender": {
            "full_name": "Sender", "phone": "+7",
            "city": "Almaty", "address": "A",
            "geography_guid": "sender-guid",
        },
        "recipient": {
            "full_name": "Recv", "phone": "+7",
            "city": "Astana", "address": "B",
            "geography_guid": "recv-guid",
            "urgency_guid": "urg-1",
        },
        "packages": [{"weight_kg": 1.0, "quantity": 1, "description": "box"}],
        "cargo_type_guid": "cargo-1",
    }
    base.update(overrides)
    return base


class _FakeResponse:
    """SaveWaybillOffice OK envelope with a fixed waybill number."""
    def __init__(self):
        self.status_code = 200
        self.text = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:m="http://www.cargo3.ru">'
            '<soap:Body><m:SaveWaybillOfficeResponse><m:return>'
            '<m:Items><m:Value>CSE-000042</m:Value><m:Error>false</m:Error></m:Items>'
            '</m:return></m:SaveWaybillOfficeResponse></soap:Body>'
            '</soap:Envelope>'
        )


class TestNoCodPath:
    def test_defaults_sender_bank_transfer(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured.setdefault("body", content)
            return _FakeResponse()

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            waybill = client.create_waybill(
                _order_data(), {"login": "u", "password": "p", "api_url": "http://x"},
            )
        assert waybill == "CSE-000042"

        body = captured["body"].decode()
        assert "<m:TypeOfPayer>0</m:TypeOfPayer>" in body
        assert "<m:WayOfPayment>1</m:WayOfPayment>" in body
        assert "<m:AmountCOD>" not in body
        assert "<m:PaymentByRecipient>" not in body


class TestCodEnabled:
    def test_cash_cod_kzt(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured.setdefault("body", content)
            return _FakeResponse()

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_waybill(
                _order_data(cod={"amount": 12500.50, "currency": "KZT", "payment_method": "cash"}),
                {"login": "u", "password": "p", "api_url": "http://x"},
            )

        body = captured["body"].decode()
        assert "<m:TypeOfPayer>1</m:TypeOfPayer>" in body
        assert "<m:WayOfPayment>2</m:WayOfPayment>" in body
        assert "<m:AmountCOD>12500.50</m:AmountCOD>" in body
        # KZT currency GUID
        assert "<m:CurrencyCOD>d3a2419e-e7e9-11e8-80c1-7cd30aec6901</m:CurrencyCOD>" in body
        assert "<m:PaymentByRecipient>true</m:PaymentByRecipient>" in body

    def test_card_cod(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured.setdefault("body", content)
            return _FakeResponse()

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_waybill(
                _order_data(cod={"amount": 5000, "currency": "KZT", "payment_method": "card"}),
                {"login": "u", "password": "p", "api_url": "http://x"},
            )
        body = captured["body"].decode()
        assert "<m:WayOfPayment>3</m:WayOfPayment>" in body

    def test_cod_xml_lives_inside_cargo(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured.setdefault("body", content)
            return _FakeResponse()

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_waybill(
                _order_data(cod={"amount": 100, "currency": "KZT"}),
                {"login": "u", "password": "p", "api_url": "http://x"},
            )
        body = captured["body"].decode()
        cargo = re.search(r"<m:Cargo>.*?</m:Cargo>", body, re.DOTALL)
        assert cargo is not None
        assert "<m:AmountCOD>" in cargo.group(0)
        assert "<m:PaymentByRecipient>" in cargo.group(0)


class TestCodValidation:
    def test_unknown_currency_raises_before_api_call(self):
        called = []

        def fake_post(url, content, headers, timeout):
            called.append(1)
            return _FakeResponse()

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(RuntimeError, match="unsupported COD currency"):
                client.create_waybill(
                    _order_data(cod={"amount": 100, "currency": "XYZ"}),
                    {"login": "u", "password": "p", "api_url": "http://x"},
                )
        assert not called, "must not hit the API when currency is unsupported"

    def test_zero_amount_treats_as_no_cod(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured.setdefault("body", content)
            return _FakeResponse()

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_waybill(
                _order_data(cod={"amount": 0}),
                {"login": "u", "password": "p", "api_url": "http://x"},
            )
        body = captured["body"].decode()
        assert "<m:AmountCOD>" not in body
        assert "<m:TypeOfPayer>0</m:TypeOfPayer>" in body
