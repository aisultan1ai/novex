"""P0-4: Tracking по ClientNumber возвращает и прямую, и возвратную накладную.

Проверяем, что:
  * request-инвариант — CSE получает два <m:List> ключа, когда client_number передан;
  * client_number == waybill_number не дублируется в запросе;
  * события из обоих ключей дедуплицируются по (guid, occurred_at).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from unittest.mock import patch

from app.modules.carriers.api_clients.cse import CSEAPIClient


_NS = 'xmlns:m="http://www.cargo3.ru"'


def _build_response(events_by_key: dict[str, list[tuple[str, str, str]]]) -> str:
    """Build a CSE Tracking SOAP envelope. events_by_key is
    {doc_key: [(status_name, guid, datetime), ...]}."""
    docs_xml = ""
    for doc_key, evs in events_by_key.items():
        events_xml = "".join(
            f'<m:List>'
            f'<m:Key>{name}</m:Key>'
            f'<m:Properties><m:Key>GUID</m:Key><m:Value>{guid}</m:Value>'
            f'<m:ValueType>string</m:ValueType></m:Properties>'
            f'<m:Properties><m:Key>DateTime</m:Key><m:Value>{when}</m:Value>'
            f'<m:ValueType>dateTime</m:ValueType></m:Properties>'
            f'</m:List>'
            for name, guid, when in evs
        )
        docs_xml += (
            f'<m:List><m:Key>{doc_key}</m:Key>{events_xml}</m:List>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:m="http://www.cargo3.ru">'
        '<soap:Body>'
        f'<m:TrackingResponse><m:return>{docs_xml}</m:return></m:TrackingResponse>'
        '</soap:Body>'
        '</soap:Envelope>'
    )


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


class TestTrackingRequestXml:
    def test_client_number_adds_second_lookup_key(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_build_response({"CSE-001": []}))

        client = CSEAPIClient()
        creds = {"api_url": "http://x", "login": "u", "password": "p"}
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.tracking("CSE-001", creds, client_number="NOVEX-000042")

        body = captured["body"].decode()
        # Should have two doc lookup keys inside <m:documents>.
        docs_block = body.split("<m:documents>")[1].split("</m:documents>")[0]
        keys = re.findall(r"<m:List><m:Key>([^<]+)</m:Key></m:List>", docs_block)
        assert "CSE-001" in keys
        assert "NOVEX-000042" in keys

    def test_no_duplicate_key_when_client_number_equals_waybill(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_build_response({"X": []}))

        client = CSEAPIClient()
        creds = {"api_url": "http://x", "login": "u", "password": "p"}
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.tracking("SAME", creds, client_number="SAME")

        body = captured["body"].decode()
        docs_block = body.split("<m:documents>")[1].split("</m:documents>")[0]
        keys = re.findall(r"<m:List><m:Key>([^<]+)</m:Key></m:List>", docs_block)
        assert keys == ["SAME"]

    def test_none_client_number_keeps_single_key(self):
        captured: dict[str, bytes] = {}

        def fake_post(url, content, headers, timeout):
            captured["body"] = content
            return _FakeResponse(_build_response({"A": []}))

        client = CSEAPIClient()
        creds = {"api_url": "http://x", "login": "u", "password": "p"}
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            client.tracking("A", creds)  # no client_number

        body = captured["body"].decode()
        docs_block = body.split("<m:documents>")[1].split("</m:documents>")[0]
        keys = re.findall(r"<m:List><m:Key>([^<]+)</m:Key></m:List>", docs_block)
        assert keys == ["A"]


class TestTrackingDedup:
    def test_same_event_in_both_lookups_deduped(self):
        # CSE returns the same "Груз принят" event under both keys —
        # once for the outbound doc, once for the return doc lookup.
        # Expected: single entry in the merged list.
        response = _build_response({
            "CSE-001": [("Груз принят", "guid-1", "2026-09-21T09:00:00")],
            "NOVEX-000042": [
                ("Груз принят", "guid-1", "2026-09-21T09:00:00"),
                # Return-leg-only event:
                ("Возврат отправителю", "guid-2", "2026-09-30T15:00:00"),
            ],
        })

        def fake_post(url, content, headers, timeout):
            return _FakeResponse(response)

        client = CSEAPIClient()
        creds = {"api_url": "http://x", "login": "u", "password": "p"}
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            events = client.tracking("CSE-001", creds, client_number="NOVEX-000042")

        guids = [e["guid"] for e in events]
        assert guids == ["guid-1", "guid-2"]
        # Chronological order preserved.
        assert events[0]["occurred_at"] < events[1]["occurred_at"]

    def test_backward_compat_without_client_number(self):
        response = _build_response({
            "CSE-001": [
                ("Отправление принято", "g1", "2026-09-21T09:00:00"),
                ("Отправлено", "g2", "2026-09-21T15:00:00"),
            ],
        })

        def fake_post(url, content, headers, timeout):
            return _FakeResponse(response)

        client = CSEAPIClient()
        creds = {"api_url": "http://x", "login": "u", "password": "p"}
        with patch("app.modules.carriers.api_clients.cse.httpx.post", fake_post):
            events = client.tracking("CSE-001", creds)

        assert len(events) == 2
