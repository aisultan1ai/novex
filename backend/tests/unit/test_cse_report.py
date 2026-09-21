"""P2-1: CSE Report method — invoice detail, COD agent, stock, etc."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.carriers.api_clients.cse import CSEAPIClient


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def _report_envelope(rows: list[dict]) -> str:
    def _fields_xml(row: dict) -> str:
        out = []
        for k, v in row.items():
            if isinstance(v, bool):
                vtype = "boolean"
                v_str = "true" if v else "false"
            elif isinstance(v, int):
                vtype, v_str = "int", str(v)
            elif isinstance(v, float):
                vtype, v_str = "float", f"{v}"
            else:
                vtype, v_str = "string", str(v)
            out.append(
                f'<m:Fields><m:Key>{k}</m:Key><m:Value>{v_str}</m:Value>'
                f'<m:ValueType>{vtype}</m:ValueType></m:Fields>'
            )
        return "".join(out)

    items = "".join(f'<m:List>{_fields_xml(r)}</m:List>' for r in rows)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:m="http://www.cargo3.ru">'
        f'<soap:Body><m:ReportResponse><m:return>{items}</m:return>'
        '</m:ReportResponse></soap:Body></soap:Envelope>'
    )


class TestReportRequest:
    def test_invoices_report_shape(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_report_envelope([
                {"Number": "INV-1", "Amount": 123.45, "Paid": True},
                {"Number": "INV-2", "Amount": 200.0, "Paid": False},
            ]))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            rows = client.get_report(
                "invoices",
                date_from="2026-09-01",
                date_to="2026-09-30",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )
        assert rows == [
            {"Number": "INV-1", "Amount": 123.45, "Paid": True},
            {"Number": "INV-2", "Amount": 200.0, "Paid": False},
        ]

        body = captured["body"].decode()
        assert "<m:Value>Report</m:Value>" in body   # Reference name
        assert "<m:Value>ДетализацияСчетов</m:Value>" in body
        assert "<m:Value>2026-09-01T00:00:00</m:Value>" in body
        assert "<m:Value>2026-09-30T00:00:00</m:Value>" in body

    def test_cod_agent_report(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_report_envelope([]))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.get_report(
                "cod_agent",
                date_from="2026-09-01",
                date_to="2026-09-30",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )
        body = captured["body"].decode()
        assert "<m:Value>ОтчетАгентаCOD</m:Value>" in body

    def test_extra_params_passed_through(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_report_envelope([]))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.get_report(
                "invoices",
                date_from="2026-09-01",
                date_to="2026-09-30",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
                extra_params={"Currency": "KZT"},
            )
        body = captured["body"].decode()
        assert "<m:Key>Currency</m:Key><m:Value>KZT</m:Value>" in body

    def test_datetime_input_preserved(self):
        # Callers who already have a full ISO datetime should not get "T00:00:00" appended.
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_report_envelope([]))

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.get_report(
                "invoices",
                date_from="2026-09-01T08:15:00",
                date_to="2026-09-30T23:59:59",
                creds={"api_url": "http://x", "login": "u", "password": "p"},
            )
        body = captured["body"].decode()
        assert "<m:Value>2026-09-01T08:15:00</m:Value>" in body
        assert "<m:Value>2026-09-30T23:59:59</m:Value>" in body


class TestReportValidation:
    def test_unknown_report_type_raises_before_api_call(self):
        called = []

        def fake_post(url, content, headers, timeout):
            called.append(1)
            return _FakeResponse("")

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(RuntimeError, match="unknown report_type"):
                client.get_report(
                    "nonsense",
                    date_from="2026-09-01",
                    date_to="2026-09-30",
                    creds={"api_url": "http://x", "login": "u", "password": "p"},
                )
        assert not called

    def test_bubble_cse_error(self):
        # Return an envelope with Properties[Error=true, Description=03030]
        err_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:m="http://www.cargo3.ru">'
            '<soap:Body><m:ReportResponse><m:return>'
            '<m:Properties>'
            '<m:Key>Error</m:Key><m:Value>true</m:Value>'
            '<m:List><m:Key>Description</m:Key><m:Value>03030</m:Value>'
            '<m:ValueType>string</m:ValueType></m:List>'
            '</m:Properties>'
            '</m:return></m:ReportResponse></soap:Body>'
            '</soap:Envelope>'
        )

        def fake_post(url, content, headers, timeout):
            return _FakeResponse(err_xml)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            with pytest.raises(RuntimeError, match=r"\[03030\]"):
                client.get_report(
                    "invoices",
                    date_from="2026-09-01",
                    date_to="2026-09-30",
                    creds={"api_url": "http://x", "login": "u", "password": "p"},
                )
