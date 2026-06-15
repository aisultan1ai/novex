from __future__ import annotations

import pytest

from app.common.status_machine import (
    InvalidTransitionError,
    can_transition,
    transition_order,
)


class TestTransitionOrder:
    def test_draft_to_details_completed(self):
        transition_order("draft", "shipment_details_completed")

    def test_draft_to_cancelled(self):
        transition_order("draft", "cancelled")

    def test_details_completed_to_checkout(self):
        transition_order("shipment_details_completed", "ready_for_checkout")

    def test_paid_to_dispatch_queued(self):
        transition_order("paid", "dispatch_queued")

    def test_in_transit_to_delivered(self):
        transition_order("in_transit", "delivered")

    def test_payment_rejected_can_retry(self):
        transition_order("payment_rejected", "awaiting_payment")

    def test_dispatch_failed_can_requeue(self):
        transition_order("dispatch_failed", "dispatch_queued")

    def test_invalid_transition_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_order("draft", "paid")

    def test_error_message_includes_current_status(self):
        with pytest.raises(InvalidTransitionError, match="draft"):
            transition_order("draft", "delivered")

    def test_terminal_returned_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_order("returned", "draft")

    def test_terminal_cancelled_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_order("cancelled", "draft")

    def test_unknown_status_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_order("nonexistent_status", "draft")

    def test_skipping_states_raises(self):
        with pytest.raises(InvalidTransitionError):
            transition_order("draft", "in_transit")


class TestCanTransition:
    def test_returns_true_for_valid(self):
        assert can_transition("draft", "shipment_details_completed") is True

    def test_returns_true_for_cancel(self):
        assert can_transition("draft", "cancelled") is True

    def test_returns_false_for_skip(self):
        assert can_transition("draft", "paid") is False

    def test_returns_false_for_backwards(self):
        assert can_transition("delivered", "draft") is False

    def test_unknown_status_returns_false(self):
        assert can_transition("nonexistent_status", "draft") is False

    def test_terminal_returned_false(self):
        assert can_transition("returned", "draft") is False

    def test_terminal_cancelled_false(self):
        assert can_transition("cancelled", "awaiting_payment") is False

    def test_payment_rejected_retry(self):
        assert can_transition("payment_rejected", "awaiting_payment") is True

    def test_dispatch_failed_requeue(self):
        assert can_transition("dispatch_failed", "dispatch_queued") is True
