from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from app.modules.commissions.service import CommissionsService


class TestCalculate:
    def setup_method(self):
        self.svc = CommissionsService(repo=MagicMock())

    def test_percentage_type(self):
        result = self.svc._calculate(
            gross_amount=Decimal("10000"),
            commission_type="percentage",
            commission_rate=Decimal("0.05"),
            fixed_amount=Decimal("0"),
        )
        assert result == Decimal("500.00")

    def test_fixed_type_ignores_gross(self):
        result = self.svc._calculate(
            gross_amount=Decimal("99999"),
            commission_type="fixed",
            commission_rate=Decimal("0"),
            fixed_amount=Decimal("250"),
        )
        assert result == Decimal("250.00")

    def test_combined_type(self):
        # 10000 * 0.03 + 100 = 400
        result = self.svc._calculate(
            gross_amount=Decimal("10000"),
            commission_type="combined",
            commission_rate=Decimal("0.03"),
            fixed_amount=Decimal("100"),
        )
        assert result == Decimal("400.00")

    def test_rounds_to_two_decimal_places(self):
        # 333.33 * 0.10 = 33.333 → rounds to 33.33
        result = self.svc._calculate(
            gross_amount=Decimal("333.33"),
            commission_type="percentage",
            commission_rate=Decimal("0.10"),
            fixed_amount=Decimal("0"),
        )
        assert result == Decimal("33.33")

    def test_zero_gross_percentage_gives_zero(self):
        result = self.svc._calculate(
            gross_amount=Decimal("0"),
            commission_type="percentage",
            commission_rate=Decimal("0.05"),
            fixed_amount=Decimal("0"),
        )
        assert result == Decimal("0.00")

    def test_combined_zero_rate_equals_fixed(self):
        result = self.svc._calculate(
            gross_amount=Decimal("5000"),
            commission_type="combined",
            commission_rate=Decimal("0"),
            fixed_amount=Decimal("200"),
        )
        assert result == Decimal("200.00")

    def test_result_is_decimal(self):
        result = self.svc._calculate(
            gross_amount=Decimal("1000"),
            commission_type="percentage",
            commission_rate=Decimal("0.10"),
            fixed_amount=Decimal("0"),
        )
        assert isinstance(result, Decimal)

    def test_unknown_type_falls_through_to_combined(self):
        # Any type not "percentage" or "fixed" uses the combined formula
        result = self.svc._calculate(
            gross_amount=Decimal("1000"),
            commission_type="custom",
            commission_rate=Decimal("0.10"),
            fixed_amount=Decimal("50"),
        )
        assert result == Decimal("150.00")
