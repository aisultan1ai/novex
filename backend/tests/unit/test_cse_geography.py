"""P0-5: KZ known-GUIDs fast-path in cse_geography.

Verifies that:
  * `_KZ_KNOWN_GUIDS` covers Актау and other regional centres (regression:
    Актау lives inside Мангистауская область in the XML directory);
  * `get_city_guid` short-circuits on the fast-path — no Redis / API call;
  * aliases (Kazakh + English transliteration + legacy names) resolve to the
    same GUID.
"""
from __future__ import annotations

from unittest.mock import patch

from app.modules.carriers.cse_geography import (
    _KZ_KNOWN_GUIDS,
    city_to_known_guid,
    city_to_postcode_geo,
    get_city_guid,
)


class TestKnownGuidsCoverage:
    def test_aktau_is_known(self):
        # Regression: Актау г = 189ad5c4-... inside Мангистауская область.
        assert _KZ_KNOWN_GUIDS["актау"] == "189ad5c4-4fec-11dc-bda1-0015170f8c09"

    def test_three_cities_of_republican_status_registered(self):
        assert _KZ_KNOWN_GUIDS["алматы"] == "189ad5cd-4fec-11dc-bda1-0015170f8c09"
        assert _KZ_KNOWN_GUIDS["астана"] == "189ad5d6-4fec-11dc-bda1-0015170f8c09"
        assert _KZ_KNOWN_GUIDS["шымкент"] == "189ad6b4-4fec-11dc-bda1-0015170f8c09"

    def test_english_transliteration_alias(self):
        assert city_to_known_guid("Almaty") == city_to_known_guid("алматы")
        assert city_to_known_guid("aktau") == city_to_known_guid("актау")

    def test_kazakh_and_legacy_name_aliases(self):
        # Оскемен == Усть-Каменогорск
        assert city_to_known_guid("Оскемен") == city_to_known_guid("Усть-Каменогорск")
        # Нур-Султан == Астана (2019 → 2022 rename undone)
        assert city_to_known_guid("Нур-Султан") == city_to_known_guid("Астана")
        # Конаев (2022) == Капшагай (legacy)
        assert city_to_known_guid("Конаев") == city_to_known_guid("Капшагай")

    def test_unknown_city_returns_none(self):
        assert city_to_known_guid("Не существует") is None
        assert city_to_known_guid("") is None


class TestGetCityGuidFastPath:
    def test_known_city_short_circuits_before_redis(self):
        # Neither Redis nor API should be touched for a hardcoded city.
        with patch("app.core.redis.get_redis") as redis_mock, \
             patch("app.modules.carriers.api_clients.cse.CSEAPIClient") as client_mock:
            result = get_city_guid("Алматы", creds={"login": "x", "password": "y"})
        assert result == "189ad5cd-4fec-11dc-bda1-0015170f8c09"
        redis_mock.assert_not_called()
        client_mock.assert_not_called()


class TestPostcodeStillWorks:
    def test_postcode_returned_for_known_kz_city(self):
        assert city_to_postcode_geo("Алматы") == "postcode-KZ-050000"
        assert city_to_postcode_geo("Актау") == "postcode-KZ-130000"

    def test_postcode_none_for_unknown(self):
        assert city_to_postcode_geo("Не существует") is None
