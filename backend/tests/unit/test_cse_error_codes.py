"""Regression tests for CSE Web API error-code handling."""
from __future__ import annotations

import pytest

from app.modules.carriers.api_clients.cse import extract_return
from app.modules.carriers.cse_error_codes import (
    CSEErrorCategory,
    SAVE_WAYBILL_OFFICE_TEXT_MARKERS,
    category,
    classify_freeform_error,
    describe,
    format_error,
)


_ENVELOPE_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:m="http://www.cargo3.ru">'
    '<soap:Body>'
    '<m:{method}Response>'
    '<m:return>'
    '{body}'
    '</m:return>'
    '</m:{method}Response>'
    '</soap:Body>'
    '</soap:Envelope>'
)


def _error_envelope(method: str, code: str, info: str = "") -> str:
    info_xml = (
        '<m:List><m:Key>Info</m:Key><m:Value>{info}</m:Value>'
        '<m:ValueType>string</m:ValueType></m:List>'
    ).format(info=info) if info else ""
    body = (
        '<m:Properties>'
        '<m:Key>Error</m:Key><m:Value>true</m:Value>'
        '<m:List><m:Key>Description</m:Key><m:Value>{code}</m:Value>'
        '<m:ValueType>string</m:ValueType></m:List>'
        '{info}'
        '</m:Properties>'
    ).format(code=code, info=info_xml)
    return _ENVELOPE_TEMPLATE.format(method=method, body=body)


class TestErrorCodeRegistry:
    def test_auth_error_maps_to_03010(self):
        assert category("03010") == CSEErrorCategory.AUTH
        assert "неверный логин" in describe("03010").lower()

    def test_02011_is_request_params_not_auth(self):
        # Regression: pre-fix, 02011 was labelled as auth error.
        assert category("02011") == CSEErrorCategory.REQUEST_PARAMS
        assert "неверно сформированы" in describe("02011").lower()

    def test_geography_validation(self):
        assert category("05042") == CSEErrorCategory.VALIDATION
        assert category("05041") == CSEErrorCategory.VALIDATION

    def test_print_form_category(self):
        assert category("06010") == CSEErrorCategory.PRINT_FORM
        assert category("06020") == CSEErrorCategory.PRINT_FORM

    def test_service_down(self):
        assert category("01010") == CSEErrorCategory.SERVICE_DOWN

    def test_not_found_family(self):
        assert category("04020") == CSEErrorCategory.NOT_FOUND
        assert category("04032") == CSEErrorCategory.NOT_FOUND  # ClientNumber уже используется

    def test_unknown_code_defaults_to_other(self):
        assert category("99999") == CSEErrorCategory.OTHER
        assert "неизвестный код" in describe("99999").lower()

    def test_empty_code(self):
        assert "неизвестная ошибка" in describe("").lower()

    def test_format_error_includes_code_and_hint(self):
        msg = format_error("Calc", "05042", "sender=postcode-KZ-000000")
        assert "[05042]" in msg
        assert "географи" in msg.lower()
        assert "postcode" in msg


class TestExtractReturnRaisesTypedErrors:
    def test_auth_error_bubbles_up_with_code(self):
        xml = _error_envelope("Calc", "03010")
        with pytest.raises(RuntimeError) as exc:
            extract_return(xml, "Calc")
        assert "[03010]" in str(exc.value)
        assert "неверный логин" in str(exc.value).lower()

    def test_02011_now_reads_as_params_not_auth(self):
        xml = _error_envelope("GetReferenceData", "02011")
        with pytest.raises(RuntimeError) as exc:
            extract_return(xml, "GetReferenceData")
        msg = str(exc.value).lower()
        assert "[02011]" in msg
        # Must NOT claim it's an auth error anymore.
        assert "неверный логин" not in msg
        assert "неверно сформированы" in msg

    def test_geography_error_includes_info_hint(self):
        xml = _error_envelope("SaveWaybillOffice", "05042", info="RecipientGeography=abc-123")
        with pytest.raises(RuntimeError) as exc:
            extract_return(xml, "SaveWaybillOffice")
        msg = str(exc.value)
        assert "[05042]" in msg
        assert "RecipientGeography=abc-123" in msg

    def test_unknown_code_still_raises(self):
        xml = _error_envelope("Tracking", "88888")
        with pytest.raises(RuntimeError) as exc:
            extract_return(xml, "Tracking")
        assert "[88888]" in str(exc.value)


class TestFreeformClassifier:
    def test_serial_or_uin_conflict(self):
        text = "Может быть передано только одно значение, «SerialNumber» или «UIN» в строке: 3"
        assert classify_freeform_error(text, SAVE_WAYBILL_OFFICE_TEXT_MARKERS) == "serial_or_uin_conflict"

    def test_invalid_datetime(self):
        text = "Некорректный формат даты, необходимо использовать тип «dateTime»"
        assert classify_freeform_error(text, SAVE_WAYBILL_OFFICE_TEXT_MARKERS) == "invalid_datetime"

    def test_no_match_returns_none(self):
        assert classify_freeform_error("что-то другое", SAVE_WAYBILL_OFFICE_TEXT_MARKERS) is None

    def test_empty_input(self):
        assert classify_freeform_error("", SAVE_WAYBILL_OFFICE_TEXT_MARKERS) is None
