"""
cse_geography.py — maps KZ city names to CSE geography identifiers.

CSE accepts two identifier formats for Kazakhstan cities:
  1. Postal-code format:  postcode-KZ-050000  (fast, no API call needed)
  2. GUID:               {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}  (from Geography API)

Quote flow (Calc) uses postal-code format — no API round-trip.
Dispatch flow (SaveWaybillOffice) needs GUIDs — resolved via Geography API
and cached in Redis for 24 h.
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
# Geography GUID lookup with Redis cache (for dispatch / SaveWaybillOffice)
# ---------------------------------------------------------------------------

_CACHE_TTL = 86_400  # 24 hours
_CACHE_PREFIX = "cse:geo:"


def get_city_guid(city: str, creds: dict) -> str | None:
    """
    Return the CSE Geography GUID for a city name.
    Checks Redis cache first; on miss, calls GetReferenceData → Geography.
    Returns None if the city cannot be resolved.
    """
    normalized = _normalize(city)
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
