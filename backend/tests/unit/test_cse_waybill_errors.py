"""P1-4: Structured parsing of SaveWaybillOffice validation errors."""
from __future__ import annotations

import pytest

from app.modules.carriers.cse_error_codes import (
    CSEWaybillValidationError,
    parse_save_waybill_error,
)


class TestNumericCodePath:
    def test_geography_error_with_code(self):
        exc = parse_save_waybill_error("05042", "RecipientGeography=abc")
        assert exc.code == "05042"
        assert "географи" in exc.message.lower()
        assert exc.raw_info == "RecipientGeography=abc"
        assert exc.slug is None

    def test_missing_urgency(self):
        exc = parse_save_waybill_error("05011", "")
        assert exc.code == "05011"
        assert "срочност" in exc.message.lower()


class TestFreeformPath:
    def test_serial_uin_conflict_extracts_row(self):
        text = (
            "Может быть передано только одно значение, «SerialNumber» "
            "или «UIN» в строке: [3]"
        )
        exc = parse_save_waybill_error("", text)
        assert exc.slug == "serial_or_uin_conflict"
        assert exc.product_row == 3

    def test_invalid_uin_extracts_value(self):
        text = 'Указан некорректный уникальный идентификатор «UIN»: "ABC123XYZ456" в строке: 7'
        exc = parse_save_waybill_error("", text)
        assert exc.slug == "invalid_uin"
        assert exc.product_row == 7
        assert exc.offending_value == "ABC123XYZ456"

    def test_invalid_datetime_no_row(self):
        exc = parse_save_waybill_error("", "Некорректный формат даты, необходимо использовать тип «dateTime»")
        assert exc.slug == "invalid_datetime"
        assert exc.product_row is None

    def test_no_match_still_returns_exception(self):
        # Unknown text — still surface it, just without a slug.
        exc = parse_save_waybill_error("", "какая-то новая ошибка КСЭ")
        assert exc.slug is None
        assert exc.raw_info == "какая-то новая ошибка КСЭ"
        assert "какая-то новая ошибка" in exc.message


class TestExceptionMessage:
    def test_summary_includes_row_and_value(self):
        exc = parse_save_waybill_error(
            "",
            'Указан некорректный уникальный идентификатор «UIN»: "BADUIN123" в строке: [2]',
        )
        msg = str(exc)
        assert "row=2" in msg
        assert "value=BADUIN123" in msg

    def test_can_be_raised_and_caught_as_runtime(self):
        # Backwards-compat guarantee: existing try/except RuntimeError blocks
        # in the dispatch pipeline must still catch these structured errors.
        with pytest.raises(RuntimeError):
            raise parse_save_waybill_error("05042", "")

    def test_typed_catch_still_works(self):
        with pytest.raises(CSEWaybillValidationError) as exc_info:
            raise parse_save_waybill_error("05042", "hint")
        assert exc_info.value.code == "05042"
