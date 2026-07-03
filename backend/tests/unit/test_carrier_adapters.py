"""Tests for CSE and Exline API client behaviour.

Covers the fixes applied 2026-07-03:
  1. Exline create_invoice puts orderno in waybill_number (tracking lookup key)
  2. Exline inshprice is sent only when insurance=True with declared_value>0
  3. Exline test_connection does not send unsupported <limit>
  4. CSE Tracking request uses DocumentType="Order" and parses events from
     direct <m:List> children (Order-level) and <m:Tables>/<m:Waybills>/<m:List>
  5. CSE delete_document wraps parameters in <m:List Key="parameters"> with
     <m:Properties> children and uses DocumentType="Order"
  6. CSE get_print_form uses <m:List> parameter children (not <m:Properties>)
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from app.modules.carriers.api_clients.cse import (
    _tracking_events_from,
    CSEAPIClient,
)
from app.modules.carriers.api_clients.exline import ExlineAPIClient


# ---------------------------------------------------------------------------
# Exline
# ---------------------------------------------------------------------------


class TestExlineCreateInvoice:
    def _order_data(self, **overrides) -> dict:
        base = {
            "order_id": 42,
            "sender": {"full_name": "Sender", "phone": "1", "city": "Almaty", "address": "A"},
            "recipient": {"full_name": "Recv", "phone": "2", "city": "Astana", "address": "B"},
            "packages": [{"weight_kg": 1.0, "quantity": 1, "description": "box"}],
            "declared_value": 0,
            "insurance": False,
            "fragile": False,
            "call_before_delivery": False,
            "tariff_code": "standard",
        }
        base.update(overrides)
        return base

    def _fake_response(self, orderno: str = "NOVEX-000042", barcode: str = "EX987") -> ET.Element:
        xml = f'<neworder><createorder orderno="{orderno}" barcode="{barcode}" error="0" errormsg=""/></neworder>'
        return ET.fromstring(xml)

    def _make_client_with_captured_xml(self) -> tuple[ExlineAPIClient, list]:
        captured: list[str] = []
        client = ExlineAPIClient()

        def fake_post_xml(xml_body: str, api_url: str) -> ET.Element:
            captured.append(xml_body)
            return self._fake_response()

        client._post_xml = fake_post_xml  # type: ignore[assignment]
        client.get_invoice_pdf = MagicMock(return_value=None)  # skip PDF fetch
        return client, captured

    def test_waybill_number_is_orderno_not_barcode(self):
        """statusreq lookup requires the orderno; storing barcode breaks tracking."""
        client, _ = self._make_client_with_captured_xml()
        creds = {"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"}

        result = client.create_invoice(self._order_data(), creds)

        assert result.waybill_number == "NOVEX-000042"
        assert result.carrier_invoice_id == "EX987"

    def test_inshprice_omitted_when_no_insurance(self):
        """inshprice must NOT be sent when insurance flag is False (even if declared_value>0).
        Sending it triggers Exline error 11 or silent upcharge."""
        client, captured = self._make_client_with_captured_xml()
        creds = {"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"}

        client.create_invoice(
            self._order_data(insurance=False, declared_value=5000),
            creds,
        )

        assert len(captured) == 1
        assert "<inshprice>" not in captured[0]

    def test_inshprice_omitted_when_declared_value_zero(self):
        client, captured = self._make_client_with_captured_xml()
        creds = {"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"}

        client.create_invoice(
            self._order_data(insurance=True, declared_value=0),
            creds,
        )

        assert "<inshprice>" not in captured[0]

    def test_inshprice_present_when_insurance_and_value(self):
        client, captured = self._make_client_with_captured_xml()
        creds = {"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"}

        client.create_invoice(
            self._order_data(insurance=True, declared_value=1500.5),
            creds,
        )

        assert "<inshprice>1500.50</inshprice>" in captured[0]

    def test_orderno_uses_novex_reference(self):
        client, captured = self._make_client_with_captured_xml()
        creds = {"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"}

        client.create_invoice(self._order_data(order_id=42), creds)

        assert 'orderno="NOVEX-000042"' in captured[0]


class TestExlineTestConnection:
    def test_no_limit_tag(self):
        """<limit> is not a documented statusreq parameter — must not appear."""
        client = ExlineAPIClient()
        captured: list[str] = []

        def fake_post_xml(xml_body: str, api_url: str) -> ET.Element:
            captured.append(xml_body)
            return ET.fromstring('<statusreport error="0"/>')

        client._post_xml = fake_post_xml  # type: ignore[assignment]
        creds = {"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"}

        assert client.test_connection(creds) is True
        assert "<limit>" not in captured[0]

    def test_auth_error_raises(self):
        client = ExlineAPIClient()

        def fake_post_xml(xml_body: str, api_url: str) -> ET.Element:
            return ET.fromstring('<statusreport error="1" errormsg="authorization error"/>')

        client._post_xml = fake_post_xml  # type: ignore[assignment]

        import pytest
        with pytest.raises(RuntimeError, match="authorization"):
            client.test_connection({"extra": "8", "login": "u", "password": "p", "api_url": "http://ex"})


# ---------------------------------------------------------------------------
# CSE
# ---------------------------------------------------------------------------


_NS_M = "http://www.cargo3.ru"
_NM = f"{{{_NS_M}}}"


def _mk_soap_envelope(method: str, return_inner: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:{method}Response xmlns:m="{_NS_M}">
      <m:return>{return_inner}</m:return>
    </m:{method}Response>
  </soap:Body>
</soap:Envelope>"""


class TestCSETrackingParsing:
    def test_parses_order_level_events_from_direct_list_children(self):
        """Per CSE docs (page 137–145), status events are direct <m:List> children
        of the document List, not inside <m:Tables>."""
        return_inner = f"""
        <m:Key>Tracking</m:Key>
        <m:List>
          <m:Key>888-0000111636</m:Key>
          <m:Value>Order</m:Value>
          <m:Properties><m:Key>DocumentType</m:Key><m:Value>Order</m:Value></m:Properties>
          <m:List>
            <m:Key>Заказ создан</m:Key>
            <m:Properties><m:Key>GUID</m:Key><m:Value>guid-1</m:Value></m:Properties>
            <m:Properties><m:Key>DateTime</m:Key><m:Value>2026-07-01T10:00:00</m:Value></m:Properties>
            <m:Properties><m:Key>Comment</m:Key><m:Value>ok</m:Value></m:Properties>
          </m:List>
          <m:List>
            <m:Key>Забран у клиента</m:Key>
            <m:Properties><m:Key>GUID</m:Key><m:Value>guid-2</m:Value></m:Properties>
            <m:Properties><m:Key>DateTime</m:Key><m:Value>2026-07-01T12:30:00</m:Value></m:Properties>
          </m:List>
        </m:List>
        """
        response = _mk_soap_envelope("Tracking", return_inner)

        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(text=response, status_code=200)
            mock_post.return_value.raise_for_status = MagicMock()
            events = client.tracking("888-0000111636", {"login": "test", "password": "2016"})

        assert len(events) == 2
        assert events[0]["status"] == "Заказ создан"
        assert events[0]["occurred_at"] == "2026-07-01T10:00:00"
        assert events[1]["status"] == "Забран у клиента"

    def test_tracking_request_uses_document_type_order(self):
        """Request must send DocumentType=Order per docs — Waybill silently
        returns nothing for orders created via SaveWaybillOffice."""
        client = CSEAPIClient()
        with patch("app.modules.carriers.api_clients.cse.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                text=_mk_soap_envelope("Tracking", "<m:Key>Tracking</m:Key>"),
                status_code=200,
            )
            mock_post.return_value.raise_for_status = MagicMock()
            client.tracking("888-000", {"login": "test", "password": "2016"})

        sent_body = mock_post.call_args.kwargs["content"].decode()
        assert "<m:Value>Order</m:Value>" in sent_body
        assert "<m:Value>Waybill</m:Value>" not in sent_body

    def test_metadata_only_lists_produce_no_event(self):
        """Metadata properties without a DateTime must NOT be treated as events."""
        # A List with no DateTime property = metadata, not a tracking event
        xml = """<m:List xmlns:m="http://www.cargo3.ru">
          <m:Key>SomeMetadata</m:Key>
          <m:Properties><m:Key>GUID</m:Key><m:Value>xxx</m:Value></m:Properties>
        </m:List>"""
        el = ET.fromstring(xml)
        assert _tracking_events_from(el) == []

    def test_event_with_datetime_is_extracted(self):
        xml = """<m:List xmlns:m="http://www.cargo3.ru">
          <m:Key>Доставлен</m:Key>
          <m:Properties><m:Key>DateTime</m:Key><m:Value>2026-07-02T09:00:00</m:Value></m:Properties>
          <m:Properties><m:Key>Recipient</m:Key><m:Value>Иванов</m:Value></m:Properties>
        </m:List>"""
        el = ET.fromstring(xml)
        events = _tracking_events_from(el)
        assert len(events) == 1
        assert events[0]["status"] == "Доставлен"
        assert events[0]["recipient"] == "Иванов"


class TestCSEDeleteDocument:
    def test_request_uses_list_with_properties(self):
        """Per docs (page 230): <m:parameters><m:Key>parameters</m:Key>
        <m:List><m:Key>parameters</m:Key><m:Properties>...</m:Properties></m:List>
        </m:parameters>. Fields at the top level silently no-ops."""
        client = CSEAPIClient()
        response = _mk_soap_envelope(
            "DeleteDocuments",
            """<m:Key>DeleteDocuments</m:Key>
               <m:List>
                 <m:Key>Order</m:Key>
                 <m:Properties><m:Key>DocumentType</m:Key><m:Value>Order</m:Value></m:Properties>
               </m:List>""",
        )
        with patch("app.modules.carriers.api_clients.cse.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(text=response, status_code=200)
            mock_post.return_value.raise_for_status = MagicMock()
            ok = client.delete_document(
                waybill_number="888-000",
                reason="test",
                contact="me",
                phone="+70000",
                creds={"login": "test", "password": "2016"},
            )

        sent_body = mock_post.call_args.kwargs["content"].decode()
        assert "<m:Key>parameters</m:Key>" in sent_body
        assert "<m:Properties><m:Key>DocumentType</m:Key><m:Value>Order</m:Value>" in sent_body
        # Confirm we no longer send the buggy Fields-based structure
        assert "<m:Fields><m:Key>DocumentType</m:Key>" not in sent_body
        assert ok is True

    def test_error_response_returns_false(self):
        client = CSEAPIClient()
        response = _mk_soap_envelope(
            "DeleteDocuments",
            """<m:Key>DeleteDocuments</m:Key>
               <m:List>
                 <m:Key>Order</m:Key>
                 <m:Properties><m:Key>Error</m:Key><m:Value>true</m:Value></m:Properties>
               </m:List>""",
        )
        with patch("app.modules.carriers.api_clients.cse.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(text=response, status_code=200)
            mock_post.return_value.raise_for_status = MagicMock()
            ok = client.delete_document(
                waybill_number="888-000",
                reason="x",
                contact="me",
                phone="+7",
                creds={"login": "test", "password": "2016"},
            )
        assert ok is False


class TestCSEGetPrintForm:
    def test_parameters_use_list_not_properties(self):
        """Per docs (page 189): parameters children are <m:List>, not <m:Properties>.
        Using Properties produces an empty BData response."""
        client = CSEAPIClient()
        import base64
        pdf_b64 = base64.b64encode(b"%PDF-1.4 dummy").decode()
        response = _mk_soap_envelope(
            "GetFormsForDocuments",
            f"""<m:Key>GetPrintForms</m:Key>
                <m:List>
                  <m:Key>888-000</m:Key>
                  <m:BData>{pdf_b64}</m:BData>
                </m:List>""",
        )
        with patch("app.modules.carriers.api_clients.cse.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(text=response, status_code=200)
            mock_post.return_value.raise_for_status = MagicMock()
            pdf = client.get_print_form("888-000", {"login": "test", "password": "2016"})

        sent_body = mock_post.call_args.kwargs["content"].decode()
        # Parameters must be List elements
        assert "<m:List><m:Key>DocumentType</m:Key><m:Value>order</m:Value>" in sent_body
        assert "<m:List><m:Key>Type</m:Key><m:Value>print</m:Value>" in sent_body
        assert "<m:List><m:Key>Format</m:Key><m:Value>pdf</m:Value>" in sent_body
        # Old broken Properties structure must be gone
        assert "<m:Properties><m:Key>DocumentType</m:Key>" not in sent_body
        assert pdf.startswith(b"%PDF")
