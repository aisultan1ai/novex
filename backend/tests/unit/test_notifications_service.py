from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.notifications.service import NotificationsService, _STATUS_TITLES


class TestStatusTitles:
    def test_paid_title(self):
        assert _STATUS_TITLES["paid"] == "Оплата подтверждена"

    def test_delivered_title(self):
        assert _STATUS_TITLES["delivered"] == "Доставлен"

    def test_cancelled_title(self):
        assert _STATUS_TITLES["cancelled"] == "Отменён"

    def test_in_transit_title(self):
        assert _STATUS_TITLES["in_transit"] == "В пути"

    def test_dispatch_failed_is_user_friendly(self):
        # The title for a failed dispatch should be friendly — not expose internal "failed"
        assert "failed" not in _STATUS_TITLES["dispatch_failed"].lower()

    def test_payment_rejected_title_mentions_retry(self):
        title = _STATUS_TITLES["payment_rejected"]
        assert "оплат" in title.lower()


class TestNotifyOrderStatus:
    def setup_method(self):
        self.repo = MagicMock()
        self.svc = NotificationsService(repo=self.repo)
        self.db = MagicMock()

    def test_creates_notification_for_known_status(self):
        with patch.object(self.svc, "_send_order_email"):
            self.svc.notify_order_status(self.db, user_id=1, order_id=42, status="paid")

        self.repo.create.assert_called_once_with(
            self.db,
            user_id=1,
            type="order_status",
            title="Оплата подтверждена",
            body="Заказ #42: оплата подтверждена",
        )

    def test_unknown_status_uses_fallback_title(self):
        with patch.object(self.svc, "_send_order_email"):
            self.svc.notify_order_status(self.db, user_id=5, order_id=7, status="unknown_xyz")

        call_kwargs = self.repo.create.call_args.kwargs
        assert "unknown_xyz" in call_kwargs["title"]

    def test_body_contains_order_id(self):
        with patch.object(self.svc, "_send_order_email"):
            self.svc.notify_order_status(self.db, user_id=1, order_id=123, status="delivered")

        call_kwargs = self.repo.create.call_args.kwargs
        assert "123" in call_kwargs["body"]

    def test_calls_send_email_with_correct_args(self):
        with patch.object(self.svc, "_send_order_email") as mock_email:
            self.svc.notify_order_status(self.db, user_id=3, order_id=10, status="paid", reject_reason=None)

        mock_email.assert_called_once_with(
            self.db, user_id=3, order_id=10, status="paid", reject_reason=None
        )

    def test_passes_reject_reason_to_email(self):
        with patch.object(self.svc, "_send_order_email") as mock_email:
            self.svc.notify_order_status(
                self.db, user_id=1, order_id=1, status="payment_rejected", reject_reason="Неверная сумма"
            )

        call_kwargs = mock_email.call_args.kwargs
        assert call_kwargs["reject_reason"] == "Неверная сумма"
