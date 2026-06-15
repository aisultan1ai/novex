from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.modules.orders.service import OrdersService


def _draft(id: int = 1, user_id: int = 1, status: str = "draft", parties=None, packages=None):
    d = MagicMock()
    d.id = id
    d.user_id = user_id
    d.status = status
    d.parties = parties if parties is not None else []
    d.packages = packages if packages is not None else []
    return d


class TestGetOrderDraft:
    def setup_method(self):
        self.repo = MagicMock()
        self.svc = OrdersService(repository=self.repo, address_book_repo=MagicMock())
        self.db = MagicMock()

    def test_not_found_raises(self):
        self.repo.get_order_draft_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.svc.get_order_draft(self.db, user_id=1, draft_id=99)

    def test_wrong_user_raises_forbidden(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=2)
        with pytest.raises(ForbiddenError):
            self.svc.get_order_draft(self.db, user_id=1, draft_id=1)

    def test_success_returns_response(self):
        draft = _draft(user_id=1)
        self.repo.get_order_draft_by_id.return_value = draft
        mock_response = MagicMock()
        with patch.object(self.svc, "_build_order_draft_response", return_value=mock_response):
            result = self.svc.get_order_draft(self.db, user_id=1, draft_id=1)
        assert result is mock_response


class TestDeleteDraft:
    def setup_method(self):
        self.repo = MagicMock()
        self.svc = OrdersService(repository=self.repo, address_book_repo=MagicMock())
        self.db = MagicMock()

    def test_not_found_raises(self):
        self.repo.get_order_draft_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.svc.delete_draft(self.db, user_id=1, draft_id=99)

    def test_wrong_user_raises_forbidden(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=2)
        with pytest.raises(ForbiddenError):
            self.svc.delete_draft(self.db, user_id=1, draft_id=1)

    def test_paid_status_cannot_be_deleted(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=1, status="paid")
        with pytest.raises(ValidationError):
            self.svc.delete_draft(self.db, user_id=1, draft_id=1)

    def test_in_transit_cannot_be_deleted(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=1, status="in_transit")
        with pytest.raises(ValidationError):
            self.svc.delete_draft(self.db, user_id=1, draft_id=1)

    def test_success_calls_repo_delete(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=1, status="draft")
        self.svc.delete_draft(self.db, user_id=1, draft_id=1)
        self.repo.delete_order_draft_by_id.assert_called_once_with(self.db, draft_id=1)

    def test_success_commits_db(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=1, status="draft")
        self.svc.delete_draft(self.db, user_id=1, draft_id=1)
        self.db.commit.assert_called_once()


class TestProceedToCheckout:
    def setup_method(self):
        self.repo = MagicMock()
        self.svc = OrdersService(repository=self.repo, address_book_repo=MagicMock())
        self.db = MagicMock()

    def test_not_found_raises(self):
        self.repo.get_order_draft_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.svc.proceed_to_checkout(self.db, user_id=1, draft_id=1)

    def test_wrong_user_raises_forbidden(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=2)
        with pytest.raises(ForbiddenError):
            self.svc.proceed_to_checkout(self.db, user_id=1, draft_id=1)

    def test_wrong_status_raises_validation(self):
        self.repo.get_order_draft_by_id.return_value = _draft(user_id=1, status="draft")
        with pytest.raises(ValidationError):
            self.svc.proceed_to_checkout(self.db, user_id=1, draft_id=1)

    def test_missing_parties_raises_validation(self):
        draft = _draft(user_id=1, status="shipment_details_completed", parties=[], packages=[MagicMock()])
        self.repo.get_order_draft_by_id.return_value = draft
        with pytest.raises(ValidationError):
            self.svc.proceed_to_checkout(self.db, user_id=1, draft_id=1)

    def test_missing_packages_raises_validation(self):
        draft = _draft(user_id=1, status="shipment_details_completed", parties=[MagicMock()], packages=[])
        self.repo.get_order_draft_by_id.return_value = draft
        with pytest.raises(ValidationError):
            self.svc.proceed_to_checkout(self.db, user_id=1, draft_id=1)

    def test_success_updates_status_to_checkout(self):
        draft = _draft(user_id=1, status="shipment_details_completed", parties=[MagicMock()], packages=[MagicMock()])
        refreshed = _draft(user_id=1, status="ready_for_checkout")
        self.repo.get_order_draft_by_id.side_effect = [draft, refreshed]
        mock_response = MagicMock()
        with patch.object(self.svc, "_build_order_draft_response", return_value=mock_response):
            result = self.svc.proceed_to_checkout(self.db, user_id=1, draft_id=1)
        self.repo.update_order_draft_status.assert_called_once_with(
            self.db, order_draft=draft, status="ready_for_checkout"
        )
        assert result is mock_response


class TestQuoteSessionPackageDescription:
    def setup_method(self):
        self.svc = OrdersService()

    def _qs(self, shipment_type: str):
        qs = MagicMock()
        qs.shipment_type = shipment_type
        return qs

    def test_document_type(self):
        assert self.svc._quote_session_package_description(self._qs("document")) == "Documents"

    def test_document_uppercase(self):
        assert self.svc._quote_session_package_description(self._qs("DOCUMENT")) == "Documents"

    def test_parcel_type(self):
        assert self.svc._quote_session_package_description(self._qs("parcel")) == "Parcel"

    def test_parcel_mixed_case(self):
        assert self.svc._quote_session_package_description(self._qs("Parcel")) == "Parcel"

    def test_unknown_type_returned_as_is(self):
        assert self.svc._quote_session_package_description(self._qs("freight")) == "freight"

    def test_blank_type_returns_shipment_fallback(self):
        assert self.svc._quote_session_package_description(self._qs("  ")) == "Shipment"
