"""
Discovery-скрипт: сверка нашего маппинга статусов с живыми ответами
перевозчиков и с реальным трафиком.

Что делает:
    1) Зовёт CSE `GetReferenceData: CargoStates` для order/waybill/trace,
       прогоняет каждое имя через наш _map_status и печатает:
         - какие фразы уходят в carrier_unknown (нужно смаппить)
         - какие семантически подозрительные (например, "доставлено"
           уехало в in_transit — сигнал о неправильном порядке ключей)
    2) Топ N carrier_status'ов из tracking_events за последние 30 дней,
       которые дают carrier_unknown в текущей семантике — приоритизация
       того, что маппить в первую очередь.

Запуск (из корня backend):
    python -m scripts.sync_carrier_states                # test-URL по умолчанию
    python -m scripts.sync_carrier_states --prod         # prod-URL
    python -m scripts.sync_carrier_states --skip-db      # без запроса к БД
    python -m scripts.sync_carrier_states --carrier cse  # фильтр по перевозчику

Не автоматизировать в cron: карrier'ы редко добавляют статусы, а поломка
автоматического маппинга тише bug'а от неправильного значения. Запускайте
разово раз в месяц вручную.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import warnings
import xml.etree.ElementTree as ET
from collections import Counter

warnings.filterwarnings("ignore")

# backend в sys.path — скрипт лежит в scripts/, стартует из backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

_NM = "{http://www.cargo3.ru}"
_GUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _fetch_cse_states(url: str, login: str, password: str, doc_type: str) -> list[tuple[str, str]]:
    """→ [(guid, name), ...] для одного DocumentType."""
    from app.modules.carriers.api_clients.cse import build_envelope

    inner = (
        f"<m:login>{login}</m:login>"
        f"<m:password>{password}</m:password>"
        "<m:parameters><m:Key>parameters</m:Key>"
        "<m:List><m:Key>Reference</m:Key><m:Value>CargoStates</m:Value>"
        "<m:ValueType>string</m:ValueType></m:List>"
        f"<m:List><m:Key>DocumentType</m:Key><m:Value>{doc_type}</m:Value>"
        "<m:ValueType>string</m:ValueType></m:List>"
        "</m:parameters>"
    )
    r = httpx.post(
        url,
        content=build_envelope("GetReferenceData", inner),
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": ""},
        timeout=30,
    )
    r.raise_for_status()
    root = ET.fromstring(r.content)

    # error-response тоже 200 OK, отличается по Properties[Key=Error]
    props = root.find(f".//{_NM}Properties")
    if props is not None:
        err = props.find(f"{_NM}Value")
        if err is not None and (err.text or "").strip().lower() == "true":
            desc_el = props.find(f".//{_NM}Value")
            desc = desc_el.text if desc_el is not None else "unknown"
            raise RuntimeError(f"CSE вернул ошибку: {desc}")

    ret = root.find(f".//{_NM}return")
    if ret is None:
        return []
    out: list[tuple[str, str]] = []
    for lst in ret.findall(f"{_NM}List"):
        k = lst.find(f"{_NM}Key")
        v = lst.find(f"{_NM}Value")
        if k is None or v is None:
            continue
        k_txt = (k.text or "").strip()
        v_txt = (v.text or "").strip()
        if _GUID_RE.match(k_txt):
            out.append((k_txt, v_txt))
    return out


def _audit_cse(url: str, login: str, password: str) -> None:
    from app.modules.carriers.polling.cse_adapter import _map_status, _UNKNOWN_STATUS

    print(f"\n{'='*70}\n  CSE — прогон {url}\n{'='*70}")
    all_states: dict[str, set[str]] = {}
    for dt in ("order", "waybill", "trace"):
        try:
            lst = _fetch_cse_states(url, login, password, dt)
        except Exception as e:
            print(f"  [{dt}] ERROR: {e}")
            continue
        print(f"  [{dt}] {len(lst)} состояний")
        for _guid, name in lst:
            all_states.setdefault(name, set()).add(dt)

    print(f"\n  UNIQUE: {len(all_states)}\n")
    unknown: list[str] = []
    suspicious: list[tuple[str, str]] = []
    for name in sorted(all_states):
        mapped = _map_status(name)
        if mapped == _UNKNOWN_STATUS:
            unknown.append(name)
            continue
        low = name.lower()
        # Sanity check: очевидные indicators должны попасть в правильную ветку
        expected = None
        if "доставл" in low or "вручен" in low:
            expected = {"delivered"}
        elif "отказ" in low and "оплат" not in low:
            expected = {"delivery_failed"}
        elif "таможн" in low:
            expected = {"customs_hold"}
        elif "отмен" in low or "аннулир" in low:
            expected = {"cancelled"}
        elif "утер" in low or "утилиз" in low:
            expected = {"delivery_failed"}
        if expected and mapped not in expected:
            suspicious.append((name, f"{mapped} — ожидалось одно из {expected}"))

    print(f"  → carrier_unknown ({len(unknown)}):")
    for n in unknown:
        print(f"     {n}")
    if suspicious:
        print(f"\n  SUSPICIOUS маппинги ({len(suspicious)}):")
        for name, note in suspicious:
            print(f"     {name}  |  {note}")


def _audit_db(carrier_filter: str | None) -> None:
    """Смотрим tracking_events за 30 дней и печатаем топ carrier_status'ов,
    которые уехали в carrier_unknown при текущем маппинге."""
    from datetime import timedelta

    from sqlalchemy import select
    from app.common.time_utils import utcnow
    from app.core.db import SessionLocal
    from app.modules.tracking.models import TrackingEvent

    since = utcnow() - timedelta(days=30)
    print(f"\n{'='*70}\n  БД: неизвестные carrier_status за 30 дней\n{'='*70}")

    with SessionLocal() as db:
        stmt = (
            select(TrackingEvent.carrier_status)
            .where(
                TrackingEvent.status == "carrier_unknown",
                TrackingEvent.occurred_at >= since,
                TrackingEvent.carrier_status.is_not(None),
            )
        )
        rows = db.scalars(stmt).all()

    if not rows:
        print("  Нет 'carrier_unknown' событий за 30 дней — либо всё хорошо, либо ")
        print("  адаптеры ещё не начали писать этот статус после обновления.")
        return

    counter = Counter(rows)
    print(f"  Всего событий: {len(rows)}. Уникальных фраз: {len(counter)}\n")
    print(f"  Топ по частоте (карrier_filter={carrier_filter or 'все'}):")
    for phrase, cnt in counter.most_common(50):
        print(f"    {cnt:5d}  |  {phrase}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod", action="store_true", help="CSE prod-URL вместо test")
    ap.add_argument("--login", default=os.getenv("CSE_LOGIN", "test"))
    ap.add_argument("--password", default=os.getenv("CSE_PASSWORD", "2016"))
    ap.add_argument("--skip-cse", action="store_true")
    ap.add_argument("--skip-db", action="store_true")
    ap.add_argument("--carrier", default=None, help="фильтр (пока используется только в вывод-заголовке)")
    args = ap.parse_args()

    if not args.skip_cse:
        from app.modules.carriers.api_clients.cse import DEFAULT_API_URL, TEST_API_URL
        url = DEFAULT_API_URL if args.prod else TEST_API_URL
        _audit_cse(url, args.login, args.password)

    if not args.skip_db:
        try:
            _audit_db(args.carrier)
        except Exception as e:
            print(f"\n  БД пропущена: {e}")


if __name__ == "__main__":
    main()
