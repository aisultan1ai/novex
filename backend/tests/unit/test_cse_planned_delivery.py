"""P0-3: `planneddeliverydate` in _tracking_events_from + delivered_at gating."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from app.modules.carriers.api_clients.cse import _tracking_events_from

_DELIVERED_GUID = "8e5ded66-a8f5-4fa8-b863-03e1e0406df5"

_NS = 'xmlns:m="http://www.cargo3.ru"'


def _make_status_item(status_name: str, properties: dict[str, str]) -> ET.Element:
    props_xml = "".join(
        f'<m:Properties><m:Key>{k}</m:Key><m:Value>{v}</m:Value>'
        f'<m:ValueType>string</m:ValueType></m:Properties>'
        for k, v in properties.items()
    )
    xml = (
        f'<m:List {_NS}>'
        f'<m:Key>{status_name}</m:Key>'
        f'{props_xml}'
        f'</m:List>'
    )
    return ET.fromstring(xml)


class TestPlannedDeliveryExtraction:
    def test_extracts_planneddeliverydate_property(self):
        item = _make_status_item("Груз в пути", {
            "GUID": "aa-bb-cc",
            "DateTime": "2026-09-21T10:00:00",
            "PlannedDeliveryDate": "2026-09-25T00:00:00",
        })
        events = _tracking_events_from(item)
        assert len(events) == 1
        assert events[0]["planned_delivery_at"] == "2026-09-25T00:00:00"

    def test_missing_planned_delivery_is_empty(self):
        item = _make_status_item("Отправление принято", {
            "GUID": "xx",
            "DateTime": "2026-09-21T10:00:00",
        })
        events = _tracking_events_from(item)
        assert events[0]["planned_delivery_at"] == ""

    def test_property_key_is_case_insensitive(self):
        # CSE sometimes emits `planneddeliverydate` in lowercase or mixed case.
        item = _make_status_item("Отправлено", {
            "guid": "x",
            "datetime": "2026-09-21T10:00:00",
            "planneddeliverydate": "2026-09-30T00:00:00",
        })
        events = _tracking_events_from(item)
        assert events[0]["planned_delivery_at"] == "2026-09-30T00:00:00"


class TestDeliveredAtGating:
    def test_delivered_at_only_for_final_guid(self):
        item = _make_status_item("Доставка успешно выполнена", {
            "GUID": _DELIVERED_GUID,
            "DateTime": "2026-09-21T15:30:00",
            "DeliveryDateTime": "2026-09-21T15:30:00",
        })
        events = _tracking_events_from(item)
        assert events[0]["delivered_at"] == "2026-09-21T15:30:00"

    def test_delivered_at_empty_for_intermediate_status(self):
        # CSE sometimes echoes PlannedDeliveryDate into DeliveryDateTime on
        # intermediate events; that must NOT be treated as fact of delivery.
        item = _make_status_item("Отправление в пути", {
            "GUID": "not-the-final-guid",
            "DateTime": "2026-09-21T09:00:00",
            "DeliveryDateTime": "2026-09-25T00:00:00",
        })
        events = _tracking_events_from(item)
        assert events[0]["delivered_at"] == ""

    def test_delivered_at_falls_back_to_datetime(self):
        # DeliveryDateTime missing on final status → use occurred_at as best-effort.
        item = _make_status_item("Доставлено", {
            "GUID": _DELIVERED_GUID,
            "DateTime": "2026-09-21T15:30:00",
        })
        events = _tracking_events_from(item)
        assert events[0]["delivered_at"] == "2026-09-21T15:30:00"


class TestNodeWithoutTimestamp:
    def test_returns_empty_when_no_datetime(self):
        # Metadata-only node (no DateTime → not an event).
        item = _make_status_item("Metadata", {"GUID": "x"})
        assert _tracking_events_from(item) == []
