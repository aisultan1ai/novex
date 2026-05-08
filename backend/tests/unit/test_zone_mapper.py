from __future__ import annotations

import pytest

from app.modules.carriers.zone_mapper import get_zone, is_known_city


class TestGetZone:
    def test_same_city_is_zone_0(self):
        assert get_zone("Алматы", "Алматы") == 0

    def test_same_city_case_insensitive(self):
        assert get_zone("алматы", "АЛМАТЫ") == 0

    def test_same_city_with_whitespace(self):
        assert get_zone("  Астана  ", "Астана") == 0

    def test_two_regional_centers_is_zone_1(self):
        assert get_zone("Алматы", "Астана") == 1
        assert get_zone("Шымкент", "Актобе") == 1
        assert get_zone("Актау", "Павлодар") == 1

    def test_regional_to_district_is_zone_2(self):
        assert get_zone("Алматы", "Экибастуз") == 2
        assert get_zone("Астана", "Темиртау") == 2

    def test_district_to_regional_is_zone_2(self):
        assert get_zone("Рудный", "Костанай") == 2

    def test_district_to_district_is_zone_2(self):
        assert get_zone("Рудный", "Экибастуз") == 2

    def test_unknown_city_is_zone_3(self):
        assert get_zone("Алматы", "Деревня Нигде") == 3
        assert get_zone("Деревня А", "Деревня Б") == 3

    def test_latin_aliases_zone_1(self):
        assert get_zone("almaty", "astana") == 1
        assert get_zone("shymkent", "aktobe") == 1

    def test_mixed_script_zone_1(self):
        assert get_zone("Алматы", "astana") == 1


class TestIsKnownCity:
    def test_regional_center_known(self):
        assert is_known_city("Алматы") is True
        assert is_known_city("almaty") is True

    def test_district_center_known(self):
        assert is_known_city("Экибастуз") is True

    def test_unknown_city(self):
        assert is_known_city("Деревня Нигде") is False
        assert is_known_city("") is False
