"""Regression tests for CSE tracking status mapping.

Covers the P0-2 change: GUID-based lookup takes priority over substring-based
name matching. CSE docs guarantee GUID stability across localised name changes,
so relying on names alone is fragile.
"""
from __future__ import annotations

from app.modules.carriers.polling.cse_adapter import (
    _STATUS_GUID_MAP,
    _UNKNOWN_STATUS,
    _map_status,
)

DELIVERED_GUID = "8e5ded66-a8f5-4fa8-b863-03e1e0406df5"


class TestGuidTakesPrecedence:
    def test_delivered_guid_is_registered(self):
        assert DELIVERED_GUID in _STATUS_GUID_MAP
        assert _STATUS_GUID_MAP[DELIVERED_GUID] == "delivered"

    def test_delivered_guid_wins_over_arbitrary_name(self):
        # Even if CSE renames the status label, GUID lookup must resolve it.
        assert _map_status("Some New Localised Name", DELIVERED_GUID) == "delivered"

    def test_guid_lookup_is_case_insensitive(self):
        assert _map_status("x", DELIVERED_GUID.upper()) == "delivered"

    def test_guid_lookup_ignores_whitespace(self):
        assert _map_status("x", f"  {DELIVERED_GUID}  ") == "delivered"


class TestSubstringFallback:
    def test_name_match_still_works_without_guid(self):
        assert _map_status("Отправление доставлено") == "delivered"

    def test_name_match_with_unknown_guid(self):
        # GUID unknown but name matches: fallback path.
        assert _map_status("Груз в пути", "00000000-0000-0000-0000-000000000000") == "in_transit"

    def test_cancellation_wins_over_generic_sent(self):
        assert _map_status("Отмена заказа") == "cancelled"

    def test_refusal_wins_over_sent(self):
        assert _map_status("Отказ в приёме отправления") == "delivery_failed"


class TestUnknownStatus:
    def test_unknown_name_and_guid_returns_placeholder(self):
        assert _map_status("Совершенно новый статус", "deadbeef-dead-beef-dead-beefdeadbeef") == _UNKNOWN_STATUS

    def test_empty_input_returns_placeholder(self):
        assert _map_status("") == _UNKNOWN_STATUS
