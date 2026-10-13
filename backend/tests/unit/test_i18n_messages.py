"""Каждый русский текст ошибки в коде должен иметь казахский перевод
(app.core.i18n._KK_EXACT / _KK_PATTERNS) или быть явно помечен как
«только русский» (app.core.i18n.RU_ONLY).

Зачем: перевод ищется по точному русскому тексту. Если кто-то поправит
формулировку в ``raise ...("...")``, перевод молча перестанет срабатывать, и
на /kz клиент увидит русскую ошибку. Этот тест ловит такие правки.
"""

from __future__ import annotations

import ast
import pathlib
import re

from app.core.i18n import RU_ONLY, translate

APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_EXC_KWARGS = {"detail", "message", "msg"}


def _is_exception_call(node: ast.Call) -> bool:
    name = getattr(node.func, "id", None) or getattr(node.func, "attr", None) or ""
    return name == "HTTPException" or name.endswith("Error") or name.endswith("Exception")


def _russian_error_literals() -> dict[str, str]:
    """{текст: "файл:строка"} для строковых литералов в вызовах исключений."""
    found: dict[str, str] = {}
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_exception_call(node):
                continue
            args = list(node.args) + [k.value for k in node.keywords if k.arg in _EXC_KWARGS]
            for arg in args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and CYRILLIC.search(arg.value):
                    found.setdefault(arg.value, f"{path.relative_to(APP_DIR.parent)}:{node.lineno}")
    return found


def test_every_russian_error_has_kazakh_translation_or_is_ru_only() -> None:
    literals = _russian_error_literals()
    assert literals, "не найдено ни одного текста ошибки — проверьте путь к app/"
    missing = [
        f"{where}: {text}"
        for text, where in sorted(literals.items(), key=lambda kv: kv[1])
        if text not in RU_ONLY and translate(text, "kk") == text
    ]
    assert not missing, (
        "Нет казахского перевода (добавьте в _KK_EXACT в app/core/i18n.py "
        "или в RU_ONLY, если текст технический):\n" + "\n".join(missing)
    )


def test_ru_only_entries_still_exist_in_code() -> None:
    """Устаревшие записи RU_ONLY (текст в коде поменяли) тоже надо чистить."""
    literals = _russian_error_literals()
    stale = sorted(t for t in RU_ONLY if t not in literals)
    assert not stale, "Этих текстов больше нет в коде, уберите их из RU_ONLY:\n" + "\n".join(stale)


def test_translate_keeps_russian_without_kk() -> None:
    assert translate("Заказ не найден.", "ru") == "Заказ не найден."
    assert translate("Заказ не найден.", "kk") == "Тапсырыс табылмады."
    assert translate("Value error, ИИН / БИН обязателен", "kk") == "Value error, ЖСН / БСН міндетті"
    assert translate("Подождите 30 сек. перед повторной отправкой письма.", "kk") == (
        "Хатты қайта жіберер алдында 30 сек күтіңіз."
    )
