"""P1-2: CreateGMH + UpdateDocuments + Марка ГМХ 10х9."""
from __future__ import annotations

import base64
import re
from unittest.mock import patch

import pytest

from app.modules.carriers.api_clients.cse import CSEAPIClient
from app.modules.carriers.cse_error_codes import CSEWaybillValidationError


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def _create_gmh_ok(guids: list[str]) -> str:
    items = "".join(
        f'<m:Items><m:GUID>{g}</m:GUID><m:Error>false</m:Error></m:Items>'
        for g in guids
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:m="http://www.cargo3.ru">'
        f'<soap:Body><m:CreateGMHResponse><m:return>{items}</m:return>'
        '</m:CreateGMHResponse></soap:Body></soap:Envelope>'
    )


def _create_gmh_err(code: str, info: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:m="http://www.cargo3.ru">'
        '<soap:Body><m:CreateGMHResponse><m:return>'
        f'<m:Items><m:Error>true</m:Error><m:ErrorInfo>{code}{": " + info if info else ""}</m:ErrorInfo></m:Items>'
        '</m:return></m:CreateGMHResponse></soap:Body></soap:Envelope>'
    )


class TestCreateCargoPlaces:
    def test_builds_items_with_client_codes(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_create_gmh_ok(["g-1", "g-2"]))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            guids = client.create_cargo_places(
                "CSE-WAY-1",
                packages=[
                    {"client_code": "BC-001", "weight_kg": 2.5, "length_cm": 30, "width_cm": 20, "height_cm": 10},
                    {"client_code": "BC-002", "weight_kg": 5.0},
                ],
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )
        assert guids == ["g-1", "g-2"]

        body = captured["body"].decode()
        assert "<m:CreateGMH>" in body
        assert "<m:Number>CSE-WAY-1</m:Number>" in body
        assert "<m:DocumentType>Waybill</m:DocumentType>" in body
        assert "<m:ClientCode>BC-001</m:ClientCode>" in body
        assert "<m:ClientCode>BC-002</m:ClientCode>" in body
        # Second package has no dims — must not emit empty Length/Width/Height.
        second_item = re.search(r"<m:Items>(?:(?!<m:Items>).)*BC-002.*?</m:Items>", body, re.DOTALL)
        assert second_item is not None
        assert "<m:Length>" not in second_item.group(0)

    def test_missing_client_code_raises(self):
        client = CSEAPIClient()
        with pytest.raises(RuntimeError, match="missing client_code"):
            client.create_cargo_places(
                "CSE-1",
                packages=[{"weight_kg": 1.0}],
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )

    def test_non_positive_weight_raises(self):
        client = CSEAPIClient()
        with pytest.raises(RuntimeError, match="weight_kg must be positive"):
            client.create_cargo_places(
                "CSE-1",
                packages=[{"client_code": "A", "weight_kg": 0}],
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )

    def test_error_05224_wrong_document_type(self):
        # 05224 = Для создания грузовых мест необходимо указать номер документа с типом Waybill
        def fake_post(url, content, headers, timeout):
            return _FakeResponse(_create_gmh_err("05224"))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(CSEWaybillValidationError) as exc_info:
                client.create_cargo_places(
                    "CSE-ORDER-1",
                    packages=[{"client_code": "A", "weight_kg": 1.0}],
                    creds={"api_url": "http://x", "login": "u", "password": "p"},
                )
        assert exc_info.value.code == "05224"


class TestUpdateWaybillDimensions:
    def _ok_envelope(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:m="http://www.cargo3.ru">'
            '<soap:Body><m:UpdateDocumentsResponse><m:return>'
            '<m:Items><m:Error>false</m:Error></m:Items>'
            '</m:return></m:UpdateDocumentsResponse></soap:Body>'
            '</soap:Envelope>'
        )

    def test_sums_weights_from_packages(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(self._ok_envelope())

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            ok = client.update_waybill_dimensions(
                "CSE-1",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
                packages=[
                    {"weight_kg": 2.0, "length_cm": 50, "width_cm": 40, "height_cm": 30},
                    {"weight_kg": 3.5},
                ],
            )
        assert ok is True
        body = captured["body"].decode()
        assert "<m:Value>5.5</m:Value>" in body  # 2.0 + 3.5
        assert "<m:Key>Weight</m:Key>" in body

    def test_explicit_totals_supported(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(self._ok_envelope())

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.update_waybill_dimensions(
                "CSE-1",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
                total_weight_kg=7.25,
                total_volume_weight_kg=8.5,
            )
        body = captured["body"].decode()
        assert "<m:Value>7.25</m:Value>" in body
        assert "<m:Value>8.5</m:Value>" in body

    def test_zero_weight_raises(self):
        client = CSEAPIClient()
        with pytest.raises(RuntimeError, match="total weight must be positive"):
            client.update_waybill_dimensions(
                "CSE-1",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
                total_weight_kg=0,
            )


class TestGmhLabels:
    def _bdata_envelope(self, payload: bytes) -> str:
        b64 = base64.b64encode(payload).decode()
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:m="http://www.cargo3.ru">'
            '<soap:Body><m:GetFormsForDocumentsResponse><m:return>'
            f'<m:List><m:BData>{b64}</m:BData></m:List>'
            '</m:return></m:GetFormsForDocumentsResponse></soap:Body>'
            '</soap:Envelope>'
        )

    def test_pdf_payload_returned(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(self._bdata_envelope(b"%PDF-fake"))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            payload = client.get_gmh_labels(
                "CSE-1",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )
        assert payload == b"%PDF-fake"

        body = captured["body"].decode()
        # Correct print-form and document type for GMH labels.
        assert "Марка ГМХ 10х9" in body
        assert "<m:Value>waybill</m:Value>" in body
        assert "<m:Value>pdf</m:Value>" in body

    def test_xlsx_format(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(self._bdata_envelope(b"PK\x03\x04"))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            payload = client.get_gmh_labels(
                "CSE-1",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
                fmt="xlsx",
            )
        assert payload.startswith(b"PK")
        body = captured["body"].decode()
        assert "<m:Value>xlsx</m:Value>" in body

    def test_bad_format_rejected_before_api_call(self):
        called = []

        def fake_post(url, content, headers, timeout):
            called.append(1)
            return _FakeResponse("")

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(RuntimeError, match="unsupported format"):
                client.get_gmh_labels(
                    "CSE-1",
                    creds={"api_url": "http://x", "login": "u", "password": "p"},
                    fmt="docx",
                )
        assert not called

    def test_get_print_form_still_pdf_only(self):
        # Regression: get_print_form (legacy) must keep its existing signature.
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(self._bdata_envelope(b"%PDF-legacy"))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            payload = client.get_print_form(
                "CSE-1",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )
        assert payload == b"%PDF-legacy"
        body = captured["body"].decode()
        assert "<m:Value>order</m:Value>" in body  # DocumentType=order for print form
        assert "<m:Value>pdf</m:Value>" in body
