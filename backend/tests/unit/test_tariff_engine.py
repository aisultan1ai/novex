from __future__ import annotations

from decimal import Decimal

from app.modules.carriers.tariff_engine import (
    _calculate_hardcoded,
    _db_rate_price,
    _economy_price,
    _lookup_standard_price,
    calculate_quotes,
    chargeable_weight,
    round_up_to_half,
)


class TestRoundUpToHalf:
    def test_exact_half(self):
        assert round_up_to_half(1.5) == 1.5

    def test_rounds_up(self):
        assert round_up_to_half(1.1) == 1.5
        assert round_up_to_half(1.6) == 2.0

    def test_exact_integer(self):
        assert round_up_to_half(2.0) == 2.0

    def test_very_small(self):
        assert round_up_to_half(0.1) == 0.5


class TestChargeableWeight:
    def test_actual_heavier(self):
        # 2 kg actual, small dimensions
        result = chargeable_weight(2.0, 1, 10, 10, 10)
        assert result == 2.0

    def test_volumetric_heavier(self):
        # 1 kg actual, but (30*30*30)/6000 = 4.5 kg volumetric
        result = chargeable_weight(1.0, 1, 30, 30, 30)
        assert result == 4.5

    def test_multiple_quantity(self):
        # 1 kg * 3 = 3 kg actual, 1 parcel volumetric small
        result = chargeable_weight(1.0, 3, 10, 10, 10)
        assert result == 3.0

    def test_rounds_up_to_half(self):
        # 0.4 kg actual → rounds up to 0.5
        result = chargeable_weight(0.4, 1, 5, 5, 5)
        assert result == 0.5


class TestLookupStandardPrice:
    def test_minimum_weight_zone0(self):
        # 0.1 kg → rounds to 0.3 tier, zone 0 → 1000
        price = _lookup_standard_price(0.3, 0)
        assert price == 1000

    def test_zone1_basic(self):
        price = _lookup_standard_price(1.0, 1)
        assert price == 2000

    def test_above_10kg_adds_extra(self):
        # 10.5 kg, zone 0: base 2435 + 1 * 125 = 2560
        price = _lookup_standard_price(10.5, 0)
        assert price == 2435 + 125

    def test_above_10kg_zone1(self):
        # 11.0 kg, zone 1: base 3125 + 2 * 160 = 3445
        price = _lookup_standard_price(11.0, 1)
        assert price == 3125 + 2 * 160


class TestEconomyPrice:
    def test_minimum_10kg_zone1(self):
        price = _economy_price(5.0, 1)
        assert price == 5500  # min 10 kg applies → base for zone 1

    def test_exact_10kg_zone2(self):
        price = _economy_price(10.0, 2)
        assert price == 7000

    def test_above_10kg_zone1(self):
        # 12 kg zone 1: base 5500 + 2 * 350 = 6200
        price = _economy_price(12.0, 1)
        assert price == 5500 + 2 * 350


class TestCalculateHardcoded:
    def test_zone0_returns_two_quotes(self):
        results = _calculate_hardcoded(0, 1.0)
        codes = {r.tariff_code for r in results}
        # Zone 0 has no economy
        assert "economy" not in codes
        assert "standard" in codes
        assert "express" in codes

    def test_zone1_returns_three_quotes(self):
        results = _calculate_hardcoded(1, 1.0)
        codes = {r.tariff_code for r in results}
        assert codes == {"standard", "express", "economy"}

    def test_sorted_by_price(self):
        results = _calculate_hardcoded(1, 5.0)
        prices = [r.price for r in results]
        assert prices == sorted(prices)

    def test_carrier_code_is_azimuth(self):
        results = _calculate_hardcoded(0, 1.0)
        assert all(r.carrier_code == "azimuth" for r in results)

    def test_returns_decimal_price(self):
        results = _calculate_hardcoded(1, 1.0)
        assert all(isinstance(r.price, Decimal) for r in results)


class TestCalculateQuotes:
    def test_no_db_uses_hardcoded(self):
        results = calculate_quotes("Алматы", "Астана", 1.0, 1, 10, 10, 10)
        assert len(results) > 0
        assert all(r.carrier_code == "azimuth" for r in results)

    def test_zone0_route(self):
        results = calculate_quotes("Алматы", "Алматы", 1.0, 1, 10, 10, 10)
        assert all(r.zone == 0 for r in results)

    def test_chargeable_kg_propagated(self):
        results = calculate_quotes("Алматы", "Астана", 2.0, 1, 10, 10, 10)
        assert all(r.chargeable_kg == 2.0 for r in results)


class TestDbRatePrice:
    """Tests for _db_rate_price helper using a simple mock object."""

    class _Rate:
        def __init__(self, base, per_price, per_weight, weight_from):
            self.base_price = base
            self.per_unit_price = per_price
            self.per_unit_weight_kg = per_weight
            self.weight_from_kg = weight_from

    def test_no_extra(self):
        rate = self._Rate(2000, None, None, 0)
        assert _db_rate_price(rate, 1.0) == 2000

    def test_with_extra(self):
        # base 3125, per 160 per 0.5 kg, from 10 kg, query 11 kg
        # excess = 1 kg → ceil(1/0.5) = 2 units → 3125 + 2*160 = 3445
        rate = self._Rate(3125, 160, 0.5, 10.0)
        assert _db_rate_price(rate, 11.0) == 3445

    def test_exact_boundary_no_extra(self):
        # At exactly weight_from, no excess
        rate = self._Rate(2000, 100, 0.5, 2.0)
        assert _db_rate_price(rate, 2.0) == 2000
