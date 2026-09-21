"""P1-1: SaveDocuments — courier pickup request."""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from app.modules.carriers.api_clients.cse import CSEAPIClient
from app.modules.carriers.cse_error_codes import CSEWaybillValidationError


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


_OK_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:m="http://www.cargo3.ru">'
    '<soap:Body><m:SaveDocumentsResponse><m:return>'
    '<m:Items><m:Value>CSE-PICKUP-42</m:Value><m:Error>false</m:Error></m:Items>'
    '</m:return></m:SaveDocumentsResponse></soap:Body>'
    '</soap:Envelope>'
)


def _err_envelope(err_info: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:m="http://www.cargo3.ru">'
        '<soap:Body><m:SaveDocumentsResponse><m:return>'
        '<m:Error>true</m:Error>'
        f'<m:ErrorInfo>{err_info}</m:ErrorInfo>'
        '</m:return></m:SaveDocumentsResponse></soap:Body>'
        '</soap:Envelope>'
    )


def _pickup_data(**overrides):
    base = {
        "sender": {
            "full_name": "Sender Ivan",
            "phone": "+77770000000",
            "geography_guid": "sender-guid",
            "address": "ул. Абая 1",
        },
        "take_date": "2026-09-25",
        "take_time_from": "10:00",
        "take_time_to": "14:00",
        "client_number": "NOVEX-000042",
        "comment": "5 коробок",
        "waybill_numbers": ["CSE-1", "CSE-2"],
    }
    base.update(overrides)
    return base


class TestRequestShape:
    def test_basic_request_contains_sender_and_take_date(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_OK_ENVELOPE)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            number = client.create_pickup_request(
                _pickup_data(),
                {"api_url": "http://x", "login": "u", "password": "p"},
            )
        assert number == "CSE-PICKUP-42"

        body = captured["body"].decode()
        assert "<m:SaveDocuments>" in body
        assert "<m:ClientNumber>NOVEX-000042</m:ClientNumber>" in body
        assert "<m:TakeDate>2026-09-25T09:00:00</m:TakeDate>" in body
        assert "<m:TakeTimeFrom>10:00</m:TakeTimeFrom>" in body
        assert "<m:TakeTimeTo>14:00</m:TakeTimeTo>" in body
        assert "<m:Comment>5 коробок</m:Comment>" in body

    def test_waybills_block_present_when_numbers_given(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_OK_ENVELOPE)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_pickup_request(
                _pickup_data(),
                {"api_url": "http://x", "login": "u", "password": "p"},
            )
        body = captured["body"].decode()
        assert "<m:Waybills><m:Items>CSE-1</m:Items><m:Items>CSE-2</m:Items></m:Waybills>" in body

    def test_waybills_omitted_when_empty(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_OK_ENVELOPE)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_pickup_request(
                _pickup_data(waybill_numbers=[]),
                {"api_url": "http://x", "login": "u", "password": "p"},
            )
        body = captured["body"].decode()
        assert "<m:Waybills>" not in body

    def test_short_take_date_gets_default_time(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_OK_ENVELOPE)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.create_pickup_request(
                _pickup_data(take_date="2026-10-01"),
                {"api_url": "http://x", "login": "u", "password": "p"},
            )
        body = captured["body"].decode()
        assert "<m:TakeDate>2026-10-01T09:00:00</m:TakeDate>" in body


class TestErrorHandling:
    def test_returns_structured_error_for_conflicting_client_number(self):
        # 04032 = ClientNumber уже используется
        def fake_post(url, content, headers, timeout):
            return _FakeResponse(_err_envelope("04032"))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(CSEWaybillValidationError) as exc_info:
                client.create_pickup_request(
                    _pickup_data(),
                    {"api_url": "http://x", "login": "u", "password": "p"},
                )
        assert exc_info.value.code == "04032"

    def test_bad_take_date_error_05103(self):
        # 05103 = «нужна другая дата забора для региона»
        def fake_post(url, content, headers, timeout):
            return _FakeResponse(_err_envelope("05103"))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(CSEWaybillValidationError) as exc_info:
                client.create_pickup_request(
                    _pickup_data(),
                    {"api_url": "http://x", "login": "u", "password": "p"},
                )
        assert exc_info.value.code == "05103"
        assert "дату забора" in exc_info.value.message.lower()

    def test_http_error_wrapped(self):
        def fake_post(url, content, headers, timeout):
            return _FakeResponse("boom", status_code=500)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(RuntimeError, match="HTTP 500"):
                client.create_pickup_request(
                    _pickup_data(),
                    {"api_url": "http://x", "login": "u", "password": "p"},
                )
