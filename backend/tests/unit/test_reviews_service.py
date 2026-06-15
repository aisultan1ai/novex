from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.modules.reviews.service import ReviewsService


def _order(user_id: int = 1, status: str = "delivered", carrier_code: str = "azimuth"):
    o = MagicMock()
    o.user_id = user_id
    o.status = status
    o.carrier_code_snapshot = carrier_code
    return o


def _payload(rating: int = 5, comment: str = "Great service"):
    p = MagicMock()
    p.rating = rating
    p.comment = comment
    return p


class TestCreateReview:
    def setup_method(self):
        self.repo = MagicMock()
        self.orders_repo = MagicMock()
        self.svc = ReviewsService(repo=self.repo, orders_repo=self.orders_repo)
        self.db = MagicMock()

    def test_order_not_found_raises(self):
        self.orders_repo.get_order_draft_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.svc.create_review(self.db, user_id=1, order_draft_id=99, payload=_payload())

    def test_wrong_user_raises_forbidden(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(user_id=2)
        with pytest.raises(ForbiddenError):
            self.svc.create_review(self.db, user_id=1, order_draft_id=1, payload=_payload())

    def test_non_reviewable_status_raises_validation(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(status="in_transit")
        with pytest.raises(ValidationError):
            self.svc.create_review(self.db, user_id=1, order_draft_id=1, payload=_payload())

    def test_draft_status_is_not_reviewable(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(status="draft")
        with pytest.raises(ValidationError):
            self.svc.create_review(self.db, user_id=1, order_draft_id=1, payload=_payload())

    def test_duplicate_review_raises_conflict(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order()
        self.repo.get_by_order_id.return_value = MagicMock()
        with pytest.raises(ConflictError):
            self.svc.create_review(self.db, user_id=1, order_draft_id=1, payload=_payload())

    def test_returned_status_is_reviewable(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(status="returned")
        self.repo.get_by_order_id.return_value = None
        mock_review = MagicMock()
        self.repo.create.return_value = mock_review

        with patch("app.modules.reviews.service.ReviewResponse.model_validate", return_value=mock_review):
            result = self.svc.create_review(self.db, user_id=1, order_draft_id=1, payload=_payload())

        self.repo.create.assert_called_once()
        assert result is mock_review

    def test_success_passes_correct_args_to_repo(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(user_id=1, carrier_code="azimuth")
        self.repo.get_by_order_id.return_value = None
        mock_review = MagicMock()
        self.repo.create.return_value = mock_review

        with patch("app.modules.reviews.service.ReviewResponse.model_validate", return_value=mock_review):
            self.svc.create_review(self.db, user_id=1, order_draft_id=42, payload=_payload(rating=4, comment="Good"))

        self.repo.create.assert_called_once_with(
            self.db,
            order_draft_id=42,
            user_id=1,
            carrier_code="azimuth",
            rating=4,
            comment="Good",
        )

    def test_success_commits_db(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order()
        self.repo.get_by_order_id.return_value = None
        self.repo.create.return_value = MagicMock()

        with patch("app.modules.reviews.service.ReviewResponse.model_validate", return_value=MagicMock()):
            self.svc.create_review(self.db, user_id=1, order_draft_id=1, payload=_payload())

        self.db.commit.assert_called_once()


class TestGetMyReview:
    def setup_method(self):
        self.repo = MagicMock()
        self.orders_repo = MagicMock()
        self.svc = ReviewsService(repo=self.repo, orders_repo=self.orders_repo)
        self.db = MagicMock()

    def test_order_not_found_raises(self):
        self.orders_repo.get_order_draft_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.svc.get_my_review(self.db, user_id=1, order_draft_id=99)

    def test_wrong_user_raises_forbidden(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(user_id=2)
        with pytest.raises(ForbiddenError):
            self.svc.get_my_review(self.db, user_id=1, order_draft_id=1)

    def test_no_review_returns_none(self):
        self.orders_repo.get_order_draft_by_id.return_value = _order(user_id=1)
        self.repo.get_by_order_id.return_value = None
        result = self.svc.get_my_review(self.db, user_id=1, order_draft_id=1)
        assert result is None
