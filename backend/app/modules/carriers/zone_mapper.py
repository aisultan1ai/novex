"""
zone_mapper.py — Azimuth-only zone lookup (FALLBACK path).

The authoritative source for Azimuth city/zone data is the `azimuth_regions`
table populated from Azimuth's own /api/integration/regions endpoint (see
azimuth_regions.py and scripts/sync_azimuth_regions.py). This module is only
consulted when the DB has no row for a given city yet — e.g. before the first
sync runs, or when a user types a city variant we do not yet have an alias for.

CSE and Exline do NOT use this — CSE has its own Geography GUID cache in
cse_geography.py, and Exline's Calc API returns its own zone number.

Zones according to the Azimuth 2026 tariff sheet:
  Зона 0 — внутригородская доставка (отправка и получение в одном городе)
  Зона 1 — пересылка между областными центрами РК
  Зона 2 — из областных центров в районные центры РК
  Зона 3 — удалённые населённые пункты
"""

from __future__ import annotations

REGIONAL_CENTERS: set[str] = {
    "актобе",
    "aktobe",
    "aktjubinsk",
    "алматы",
    "almaty",
    "алма-ата",
    "alma-ata",
    "астана",
    "astana",
    "нур-султан",
    "nur-sultan",
    "нурсултан",
    "атырау",
    "atyrau",
    "гурьев",
    "жезказган",
    "jezkazgan",
    "zhezkazgan",
    "жезкент",
    "караганда",
    "karaganda",
    "qaraghandy",
    "кокшетау",
    "kokshetau",
    "kokchetav",
    "костанай",
    "kostanay",
    "kustanay",
    "кызылорда",
    "kyzylorda",
    "qyzylorda",
    "оскемен",
    "oskemen",
    "усть-каменогорск",
    "ust-kamenogorsk",
    "павлодар",
    "pavlodar",
    "петропавловск",
    "petropavlovsk",
    "petropavl",
    "семей",
    "semey",
    "семипалатинск",
    "semipalatinsk",
    "талдыкорган",
    "taldykorgan",
    "taldiqorghan",
    "тараз",
    "taraz",
    "джамбул",
    "dzhambul",
    "уральск",
    "uralsk",
    "oral",
    "шымкент",
    "shymkent",
    "чимкент",
    "chimkent",
    "актау",
    "aktau",
    "шевченко",
}

DISTRICT_CENTERS: set[str] = {
    "аксай", "aksai",
    "жанаозен", "zhanaozen",
    "кульсары", "kulsary",
    "экибастуз", "ekibastuz",
    "степногорск", "stepnogorsk",
    "рудный", "rudny",
    "лисаковск", "lisakovsk",
    "аркалык", "arkalyk",
    "темиртау", "temirtau",
    "балхаш", "balkhash",
    "саран", "saran",
    "шахтинск", "shakhtinsk",
    "сарыагаш", "saryagash",
    "арыс", "arys",
    "кентау", "kentau",
    "туркестан", "turkestan",
    "жанакорган", "zhanakorgan",
    "риддер", "ridder",
    "лениногорск",
    "зыряновск", "zyryanovsk",
    "курчатов", "kurchatov",
    "абай", "abai",
    "приозёрск", "приозерск", "priozersk",
    "щучинск", "shchuchinsk",
    "бурабай", "burabai",
    "аксу", "aksu",
    "капшагай", "kapshagai",
    "конаев", "konaev",
    "каскелен", "kaskelen",
    "талгар", "talgar",
    "есик", "esik",
    "жаркент", "zharkent",
    "текели", "tekeli",

}


def _normalize(city: str) -> str:
    return city.strip().lower()


def get_zone(from_city: str, to_city: str) -> int:
    frm = _normalize(from_city)
    too = _normalize(to_city)

    if frm == too:
        return 0

    frm_is_regional = frm in REGIONAL_CENTERS
    too_is_regional = too in REGIONAL_CENTERS
    frm_is_district = frm in DISTRICT_CENTERS
    too_is_district = too in DISTRICT_CENTERS

    if frm_is_regional and too_is_regional:
        return 1

    if (frm_is_regional or frm_is_district) and (too_is_regional or too_is_district):
        return 2

    return 3


def is_known_city(city: str) -> bool:
    n = _normalize(city)
    return n in REGIONAL_CENTERS or n in DISTRICT_CENTERS
