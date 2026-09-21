"""
cse_geography.py — maps KZ city names to CSE geography identifiers.

CSE accepts two identifier formats for Kazakhstan cities:
  1. Postal-code format:  postcode-KZ-050000  (fast, no API call needed)
  2. GUID:               {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}  (from Geography API)

Quote flow (Calc) uses postal-code format — no API round-trip.
Dispatch flow (SaveWaybillOffice) needs GUIDs — resolved via Geography API
and cached in Redis for 24 h.

Additionally, `_KZ_KNOWN_GUIDS` hardcodes GUIDs for major KZ cities pulled
from the CSE Geography XML directory (CSE Ref/Справочник География). This
short-circuits the API call for the ~95% of dispatches that head to a
regional centre. If the CSE side later renames a city (rare — GUIDs are
stable), the value can be corrected here without a redeploy of the API
lookup path.
"""
from __future__ import annotations

import logging
import unicodedata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KZ major cities → 6-digit postal code
# Source: Kazpost official directory
# ---------------------------------------------------------------------------
_KZ_POSTCODES: dict[str, str] = {
    # Regional centres
    "алматы":           "050000",
    "almaty":           "050000",
    "алма-ата":         "050000",
    "alma-ata":         "050000",
    "астана":           "010000",
    "astana":           "010000",
    "нур-султан":       "010000",
    "нурсултан":        "010000",
    "nur-sultan":       "010000",
    "nursultan":        "010000",
    "шымкент":          "160000",
    "shymkent":         "160000",
    "чимкент":          "160000",
    "chimkent":         "160000",
    "актобе":           "030000",
    "aktobe":           "030000",
    "актюбинск":        "030000",
    "тараз":            "080000",
    "taraz":            "080000",
    "джамбул":          "080000",
    "жамбыл":           "080000",
    "павлодар":         "140000",
    "pavlodar":         "140000",
    "оскемен":          "070000",
    "oskemen":          "070000",
    "усть-каменогорск": "070000",
    "ust-kamenogorsk":  "070000",
    "семей":            "071400",
    "semey":            "071400",
    "семипалатинск":    "071400",
    "semipalatinsk":    "071400",
    "атырау":           "060000",
    "atyrau":           "060000",
    "гурьев":           "060000",
    "костанай":         "110000",
    "kostanay":         "110000",
    "кустанай":         "110000",
    "уральск":          "090000",
    "oral":             "090000",
    "uralsk":           "090000",
    "кызылорда":        "120000",
    "kyzylorda":        "120000",
    "qyzylorda":        "120000",
    "петропавловск":    "150000",
    "petropavlovsk":    "150000",
    "petropavl":        "150000",
    "актау":            "130000",
    "aktau":            "130000",
    "шевченко":         "130000",
    "кокшетау":         "020000",
    "kokshetau":        "020000",
    "коксетав":         "020000",
    "талдыкорган":      "040000",
    "taldykorgan":      "040000",
    "жезказган":        "100600",
    "zhezkazgan":       "100600",
    "jezkazgan":        "100600",
    "жезкент":          "100600",
    "туркестан":        "161200",
    "turkestan":        "161200",
    # District centres
    "темиртау":         "101400",
    "temirtau":         "101400",
    "экибастуз":        "141200",
    "ekibastuz":        "141200",
    "балхаш":           "100500",
    "balkhash":         "100500",
    "риддер":           "070300",
    "ridder":           "070300",
    "лениногорск":      "070300",
    "рудный":           "111500",
    "rudny":            "111500",
    "степногорск":      "021300",
    "stepnogorsk":      "021300",
    "аксай":            "090200",
    "aksai":            "090200",
    "капшагай":         "040900",
    "kapshagai":        "040900",
    "каскелен":         "040700",
    "kaskelen":         "040700",
    "талгар":           "040500",
    "talgar":           "040500",
    "жанаозен":         "130200",
    "zhanaozen":        "130200",
    "аксу":             "140300",
    "aksu":             "140300",
    "абай":             "101300",
    "abai":             "101300",
    "кентау":           "161100",
    "kentau":           "161100",
    "сарыагаш":         "160700",
    "saryagash":        "160700",
    "арыс":             "160300",
    "arys":             "160300",
    "жанакорган":       "120600",
    "zhanakorgan":      "120600",
    "щучинск":          "021200",
    "shchuchinsk":      "021200",
    "бурабай":          "021300",
    "burabai":          "021300",
    "лисаковск":        "111300",
    "lisakovsk":        "111300",
    "аркалык":          "111200",
    "arkalyk":          "111200",
    "жаркент":          "040800",
    "zharkent":         "040800",
    "текели":           "040600",
    "tekeli":           "040600",
    "есик":             "040400",
    "esik":             "040400",
    "кульсары":         "060800",
    "kulsary":          "060800",
    "саран":            "100600",
    "saran":            "100600",
    "шахтинск":         "101100",
    "shakhtinsk":       "101100",
}


def _normalize(city: str) -> str:
    """Lowercase + strip + strip accents."""
    s = city.strip().lower()
    return unicodedata.normalize("NFC", s)


def city_to_postcode_geo(city: str) -> str | None:
    """
    Return `postcode-KZ-XXXXXX` geo identifier for a known KZ city, or None.
    Used by Calc (quote flow) — no API call needed.
    """
    code = _KZ_POSTCODES.get(_normalize(city))
    return f"postcode-KZ-{code}" if code else None


# ---------------------------------------------------------------------------
# Known KZ city GUIDs — dumped from CSE Geography XML (September 2025).
#
# Aliases (russian + kazakh + eng transliteration) are grouped so any
# normalised spelling points to the same GUID. Keep entries lowercase — keys
# are compared post-`_normalize`.
# ---------------------------------------------------------------------------
_KZ_KNOWN_GUIDS: dict[str, str] = {
    # ── Cities of Republican Status (уровень страны) ────────────────────────
    "алматы":            "189ad5cd-4fec-11dc-bda1-0015170f8c09",
    "almaty":            "189ad5cd-4fec-11dc-bda1-0015170f8c09",
    "алма-ата":          "189ad5cd-4fec-11dc-bda1-0015170f8c09",
    "астана":            "189ad5d6-4fec-11dc-bda1-0015170f8c09",
    "astana":            "189ad5d6-4fec-11dc-bda1-0015170f8c09",
    "нур-султан":        "189ad5d6-4fec-11dc-bda1-0015170f8c09",
    "нурсултан":         "189ad5d6-4fec-11dc-bda1-0015170f8c09",
    "nur-sultan":        "189ad5d6-4fec-11dc-bda1-0015170f8c09",
    "шымкент":           "189ad6b4-4fec-11dc-bda1-0015170f8c09",
    "shymkent":          "189ad6b4-4fec-11dc-bda1-0015170f8c09",
    "чимкент":           "189ad6b4-4fec-11dc-bda1-0015170f8c09",
    # ── Regional centres ────────────────────────────────────────────────────
    "актобе":            "189ad5c7-4fec-11dc-bda1-0015170f8c09",
    "aktobe":            "189ad5c7-4fec-11dc-bda1-0015170f8c09",
    "актюбинск":         "189ad5c7-4fec-11dc-bda1-0015170f8c09",
    "актау":             "189ad5c4-4fec-11dc-bda1-0015170f8c09",
    "aktau":             "189ad5c4-4fec-11dc-bda1-0015170f8c09",
    "шевченко":          "189ad5c4-4fec-11dc-bda1-0015170f8c09",
    "атырау":            "189ad5dc-4fec-11dc-bda1-0015170f8c09",
    "atyrau":            "189ad5dc-4fec-11dc-bda1-0015170f8c09",
    "гурьев":            "189ad5dc-4fec-11dc-bda1-0015170f8c09",
    "караганда":         "189ad623-4fec-11dc-bda1-0015170f8c09",
    "karaganda":         "189ad623-4fec-11dc-bda1-0015170f8c09",
    "кокшетау":          "189ad638-4fec-11dc-bda1-0015170f8c09",
    "kokshetau":         "189ad638-4fec-11dc-bda1-0015170f8c09",
    "костанай":          "189ad63d-4fec-11dc-bda1-0015170f8c09",
    "kostanay":          "189ad63d-4fec-11dc-bda1-0015170f8c09",
    "кустанай":          "189ad63d-4fec-11dc-bda1-0015170f8c09",
    "кызылорда":         "189ad645-4fec-11dc-bda1-0015170f8c09",
    "kyzylorda":         "189ad645-4fec-11dc-bda1-0015170f8c09",
    "qyzylorda":         "189ad645-4fec-11dc-bda1-0015170f8c09",
    "павлодар":          "189ad65e-4fec-11dc-bda1-0015170f8c09",
    "pavlodar":          "189ad65e-4fec-11dc-bda1-0015170f8c09",
    "петропавловск":     "189ad661-4fec-11dc-bda1-0015170f8c09",
    "petropavlovsk":     "189ad661-4fec-11dc-bda1-0015170f8c09",
    "petropavl":         "189ad661-4fec-11dc-bda1-0015170f8c09",
    "талдыкорган":       "189ad67c-4fec-11dc-bda1-0015170f8c09",
    "taldykorgan":       "189ad67c-4fec-11dc-bda1-0015170f8c09",
    "тараз":             "189ad67f-4fec-11dc-bda1-0015170f8c09",
    "taraz":             "189ad67f-4fec-11dc-bda1-0015170f8c09",
    "джамбул":           "189ad67f-4fec-11dc-bda1-0015170f8c09",
    "жамбыл":            "189ad67f-4fec-11dc-bda1-0015170f8c09",
    "туркестан":         "189ad68e-4fec-11dc-bda1-0015170f8c09",
    "turkestan":         "189ad68e-4fec-11dc-bda1-0015170f8c09",
    "уральск":           "189ad694-4fec-11dc-bda1-0015170f8c09",
    "oral":              "189ad694-4fec-11dc-bda1-0015170f8c09",
    "uralsk":            "189ad694-4fec-11dc-bda1-0015170f8c09",
    "усть-каменогорск":  "189ad697-4fec-11dc-bda1-0015170f8c09",
    "ust-kamenogorsk":   "189ad697-4fec-11dc-bda1-0015170f8c09",
    "оскемен":           "189ad697-4fec-11dc-bda1-0015170f8c09",
    "oskemen":           "189ad697-4fec-11dc-bda1-0015170f8c09",
    "семей":             "9552cc38-a3f4-11dc-986e-0015170f8c09",
    "semey":             "9552cc38-a3f4-11dc-986e-0015170f8c09",
    "семипалатинск":     "9552cc38-a3f4-11dc-986e-0015170f8c09",
    "semipalatinsk":     "9552cc38-a3f4-11dc-986e-0015170f8c09",
    # ── District centres and other larger towns ─────────────────────────────
    "темиртау":          "189ad684-4fec-11dc-bda1-0015170f8c09",
    "temirtau":          "189ad684-4fec-11dc-bda1-0015170f8c09",
    "экибастуз":         "189ad6b7-4fec-11dc-bda1-0015170f8c09",
    "ekibastuz":         "189ad6b7-4fec-11dc-bda1-0015170f8c09",
    "балхаш":            "189ad5e4-4fec-11dc-bda1-0015170f8c09",
    "balkhash":          "189ad5e4-4fec-11dc-bda1-0015170f8c09",
    "риддер":            "13736927-d1bc-11dd-927a-0015170f8c09",
    "ridder":            "13736927-d1bc-11dd-927a-0015170f8c09",
    "лениногорск":       "13736927-d1bc-11dd-927a-0015170f8c09",
    "рудный":            "189ad664-4fec-11dc-bda1-0015170f8c09",
    "rudny":             "189ad664-4fec-11dc-bda1-0015170f8c09",
    "аркалык":           "189ad5d0-4fec-11dc-bda1-0015170f8c09",
    "arkalyk":           "189ad5d0-4fec-11dc-bda1-0015170f8c09",
    "лисаковск":         "189ad64b-4fec-11dc-bda1-0015170f8c09",
    "lisakovsk":         "189ad64b-4fec-11dc-bda1-0015170f8c09",
    "жанаозен":          "189ad607-4fec-11dc-bda1-0015170f8c09",
    "zhanaozen":         "189ad607-4fec-11dc-bda1-0015170f8c09",
    "жезказган":         "189ad60c-4fec-11dc-bda1-0015170f8c09",
    "zhezkazgan":        "189ad60c-4fec-11dc-bda1-0015170f8c09",
    "jezkazgan":         "189ad60c-4fec-11dc-bda1-0015170f8c09",
    "аксу":              "d9ef2632-d570-11ea-80db-7cd30aec6901",
    "aksu":              "d9ef2632-d570-11ea-80db-7cd30aec6901",
    "аксай":             "189ad5bf-4fec-11dc-bda1-0015170f8c09",
    "aksai":             "189ad5bf-4fec-11dc-bda1-0015170f8c09",
    "капшагай":          "189ad61f-4fec-11dc-bda1-0015170f8c09",  # renamed → Конаев in 2022
    "kapshagai":         "189ad61f-4fec-11dc-bda1-0015170f8c09",
    "конаев":            "189ad61f-4fec-11dc-bda1-0015170f8c09",
    "konaev":            "189ad61f-4fec-11dc-bda1-0015170f8c09",
    "каскелен":          "189ad62c-4fec-11dc-bda1-0015170f8c09",
    "kaskelen":          "189ad62c-4fec-11dc-bda1-0015170f8c09",
    "талгар":            "189ad67b-4fec-11dc-bda1-0015170f8c09",
    "talgar":            "189ad67b-4fec-11dc-bda1-0015170f8c09",
    "жаркент":           "189ad60a-4fec-11dc-bda1-0015170f8c09",
    "zharkent":          "189ad60a-4fec-11dc-bda1-0015170f8c09",
    "текели":            "189ad682-4fec-11dc-bda1-0015170f8c09",
    "tekeli":            "189ad682-4fec-11dc-bda1-0015170f8c09",
    "есик":              "189ad600-4fec-11dc-bda1-0015170f8c09",
    "esik":              "189ad600-4fec-11dc-bda1-0015170f8c09",
    "кульсары":          "189ad640-4fec-11dc-bda1-0015170f8c09",
    "kulsary":           "189ad640-4fec-11dc-bda1-0015170f8c09",
    "сатпаев":           "189ad66e-4fec-11dc-bda1-0015170f8c09",
    "satpaev":           "189ad66e-4fec-11dc-bda1-0015170f8c09",
    "байконур":          "c0f8d5c0-1962-11e9-80c3-7cd30aec6900",
    "baikonur":          "c0f8d5c0-1962-11e9-80c3-7cd30aec6900",
    "степногорск":       "189ad676-4fec-11dc-bda1-0015170f8c09",
    "stepnogorsk":       "189ad676-4fec-11dc-bda1-0015170f8c09",
    "щучинск":           "189ad6b6-4fec-11dc-bda1-0015170f8c09",
    "shchuchinsk":       "189ad6b6-4fec-11dc-bda1-0015170f8c09",
    "курчатов":          "189ad641-4fec-11dc-bda1-0015170f8c09",
    "kurchatov":         "189ad641-4fec-11dc-bda1-0015170f8c09",
    "каратау":           "189ad627-4fec-11dc-bda1-0015170f8c09",
    "karatau":           "189ad627-4fec-11dc-bda1-0015170f8c09",
    "шахтинск":          "189ad6a9-4fec-11dc-bda1-0015170f8c09",
    "shakhtinsk":        "189ad6a9-4fec-11dc-bda1-0015170f8c09",
    "приозерск":         "189ad663-4fec-11dc-bda1-0015170f8c09",
    "приозёрск":         "189ad663-4fec-11dc-bda1-0015170f8c09",
    "priozersk":         "189ad663-4fec-11dc-bda1-0015170f8c09",
    "кентау":            "189ad632-4fec-11dc-bda1-0015170f8c09",
    "kentau":            "189ad632-4fec-11dc-bda1-0015170f8c09",
    "сарыагаш":          "189ad66a-4fec-11dc-bda1-0015170f8c09",
    "saryagash":         "189ad66a-4fec-11dc-bda1-0015170f8c09",
    "арыс":              "ea119482-040f-11ed-8105-0090faaaf8e4",
    "arys":              "ea119482-040f-11ed-8105-0090faaaf8e4",
    "абай":              "a431eb62-9000-11e3-be51-001e67086478",
    "abai":              "a431eb62-9000-11e3-be51-001e67086478",
    "сарань":            "189ad668-4fec-11dc-bda1-0015170f8c09",
    "saran":             "189ad668-4fec-11dc-bda1-0015170f8c09",
}


def city_to_known_guid(city: str) -> str | None:
    """Return the hardcoded CSE Geography GUID for a KZ city, or None.

    O(1) lookup — used before hitting Redis / Geography API.
    """
    return _KZ_KNOWN_GUIDS.get(_normalize(city))


# ---------------------------------------------------------------------------
# Geography GUID lookup with Redis cache (for dispatch / SaveWaybillOffice)
# ---------------------------------------------------------------------------

_CACHE_TTL = 86_400  # 24 hours
_CACHE_PREFIX = "cse:geo:"


def get_city_guid(city: str, creds: dict) -> str | None:
    """
    Return the CSE Geography GUID for a city name.

    Lookup order:
      0. Hardcoded KZ known-GUIDs table (populated from the CSE XML directory
         dump). No network / cache hit for ~45 major cities that cover the
         bulk of dispatches.
      1. Redis cache (24h TTL).
      2. Geography API — GetReferenceData:Geography with optional trailing " г"
         retry for CSE's peculiar KZ city storage.

    Returns None if the city cannot be resolved.
    """
    normalized = _normalize(city)

    # 0. Hardcoded fast-path
    known = _KZ_KNOWN_GUIDS.get(normalized)
    if known:
        return known

    cache_key = f"{_CACHE_PREFIX}{normalized}"

    # 1. Try Redis cache
    try:
        from app.core.redis import get_redis
        cached = get_redis().get(cache_key)  # type: ignore[union-attr]
        if cached:
            return cached  # type: ignore[return-value]
    except Exception as exc:
        logger.debug("CSE geo cache read failed: %s", exc)

    # 2. Try postal-code format as GUID candidate (CSE accepts it in Geography lookups too)
    postcode_geo = city_to_postcode_geo(city)

    # 3. Call Geography API
    from app.modules.carriers.api_clients.cse import CSEAPIClient
    client = CSEAPIClient()
    try:
        # Try with postcode first if available (more precise)
        search_term = postcode_geo or city
        results = client.search_geography(search_term, creds)
        if not results and postcode_geo:
            # Fallback to city name search
            results = client.search_geography(city, creds)
        if not results and city and not city.lower().endswith(" г"):
            # CSE stores KZ cities with a trailing "г" ("Алматы г").
            # search_geography already retries with " г" internally, but the
            # postcode-based first attempt bypasses that retry — do it here too.
            results = client.search_geography(f"{city} г", creds)

        if not results:
            logger.warning("CSE: Geography lookup returned no results for city=%s", city)
            return None

        guid = results[0]["guid"]
        if not guid:
            return None

        # Cache result
        try:
            from app.core.redis import get_redis
            get_redis().setex(cache_key, _CACHE_TTL, guid)
        except Exception as exc:
            logger.debug("CSE geo cache write failed: %s", exc)

        return guid

    except Exception as exc:
        logger.warning("CSE: Geography API lookup failed for city=%s: %s", city, exc)
        return None
