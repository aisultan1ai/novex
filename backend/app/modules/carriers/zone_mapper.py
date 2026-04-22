"""
zone_mapper.py — определение зоны доставки Bestsender по городам.

Зоны согласно тарифным документам Bestsender 2026:
  Зона 0 — внутригородская доставка (отправка и получение в одном городе)
  Зона 1 — пересылка между областными центрами РК
  Зона 2 — из областных центров в районные центры РК (Аксай, Экибастуз, Рудный и др.)
  Зона 3 — удалённые населённые пункты от районных центров РК
"""

from __future__ import annotations

REGIONAL_CENTERS: set[str] = {
    "актобе", "aktobe", "aktjubinsk",
    "алматы", "almaty", "алма-ата", "alma-ata",
    "астана", "astana", "нур-султан", "nur-sultan", "нурсултан",
    "атырау", "atyrau", "гурьев",
    "жезказган", "jezkazgan", "zhezkazgan", "жезкент",
    "караганда", "karaganda", "qaraghandy",
    "кокшетау", "kokshetau", "kokchetav",
    "костанай", "kostanay", "kustanay",
    "кызылорда", "kyzylorda", "qyzylorda",
    "оскемен", "oskemen", "усть-каменогорск", "ust-kamenogorsk",
    "павлодар", "pavlodar",
    "петропавловск", "petropavlovsk", "petropavl",
    "семей", "semey", "семипалатинск", "semipalatinsk",
    "талдыкорган", "taldykorgan", "taldiqorghan",
    "тараз", "taraz", "джамбул", "dzhambul",
    "уральск", "uralsk", "oral",
    "шымкент", "shymkent", "чимкент", "chimkent",
    "актау", "aktau", "шевченко",
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
    "саран", "saran", "шахтинск", "shakhtinsk",
    "сарыагаш", "saryagash",
    "арыс", "arys",
    "кентау", "kentau",
    "туркестан", "turkestan",
    "жанакорган", "zhanakorgan",
    "риддер", "ridder", "лениногорск",
    "зыряновск", "zyryanovsk",
    "курчатов", "kurchatov",
    "абай", "abai",
    "приозёрск", "priozersk",
    "щучинск", "shchuchinsk", "бурабай", "burabai",
    "аксу", "aksu",
    "капшагай", "kapshagai", "каскелен", "kaskelen",
    "талгар", "talgar", "есик", "esik",
    "жаркент", "zharkent", "текели", "tekeli",
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

    if (frm_is_regional and too_is_district) or (frm_is_district and too_is_regional):
        return 2

    return 3


def is_known_city(city: str) -> bool:
    n = _normalize(city)
    return n in REGIONAL_CENTERS or n in DISTRICT_CENTERS