"""
CSE (Courier Service Express) Web API error code registry.

Source: CSE Ref/error_codes.17_11_2025 (3).pdf (Курьер Сервис Экспресс, 2025).

CSE returns errors as SOAP Properties[Error=true] with a nested List[Description=<code>].
This module maps CSE error codes → human-readable Russian messages, plus a
structured category so callers can distinguish auth failures from validation
failures without regex matching.

Two lookup functions are exposed:
  * describe(code)         — full description (localised).
  * category(code)          — CSEErrorCategory enum for programmatic handling.

Also included: SAVE_WAYBILL_OFFICE_TEXT_ERRORS — freeform substrings CSE returns
in ErrorInfo for SaveWaybillOffice (SerialNumber/UIN conflicts, dateTime format,
jewellery items) — no numeric code, only text.
"""
from __future__ import annotations

from enum import Enum


class CSEErrorCategory(str, Enum):
    """High-level grouping used to decide HTTP status / retry policy."""

    SERVICE_DOWN = "service_down"          # 01xxx  → 503
    REQUEST_PARAMS = "request_params"      # 02xxx  → 400
    AUTH = "auth"                          # 03xxx  → 401 / 403
    NOT_FOUND = "not_found"                # 04xxx  → 404 / 409
    VALIDATION = "validation"              # 05xxx  → 422
    LIST_PROPERTIES = "list_properties"    # 055xx  → 422
    PRINT_FORM = "print_form"              # 06xxx  → 502
    ECOM = "ecom"                          # 07xxx  → 422
    STATE_LOG = "state_log"                # 08xxx  → 400
    OTHER = "other"                        # 10xxx / 99xxx → 500


# ---------------------------------------------------------------------------
# Numeric error codes (exact string keys as returned by CSE in Description)
# ---------------------------------------------------------------------------

_ERROR_CODE_MAP: dict[str, tuple[str, CSEErrorCategory]] = {
    # ── 01xxx: service availability ──────────────────────────────────────
    "01010": ("Web-сервис КСЭ в текущий момент отключён", CSEErrorCategory.SERVICE_DOWN),

    # ── 02xxx: request parameters ────────────────────────────────────────
    "02010": ("Отсутствуют параметры для получения данных", CSEErrorCategory.REQUEST_PARAMS),
    "02011": ("Неверно сформированы параметры для получения данных", CSEErrorCategory.REQUEST_PARAMS),
    "02013": ("Отсутствует информация по чекам или отказано в доступе к методу", CSEErrorCategory.AUTH),
    "02020": ("Отсутствует структура для получения данных", CSEErrorCategory.REQUEST_PARAMS),
    "02021": ("Неверно сформирована структура для получения данных", CSEErrorCategory.REQUEST_PARAMS),
    "02030": ("Отсутствуют параметры для записи данных", CSEErrorCategory.REQUEST_PARAMS),
    "02031": ("Неверно сформированы параметры для записи данных", CSEErrorCategory.REQUEST_PARAMS),
    "02040": ("Отсутствует структура для записи данных", CSEErrorCategory.REQUEST_PARAMS),
    "02041": ("Неверно сформирована структура для записи данных", CSEErrorCategory.REQUEST_PARAMS),
    "02050": ("Выбранный склад не доступен по вашему договору", CSEErrorCategory.AUTH),
    "02051": ("Сервис работы со складом хранения не доступен по договору", CSEErrorCategory.AUTH),
    "02053": ("По указанным данным информация не найдена — измените географию отправителя или получателя", CSEErrorCategory.NOT_FOUND),
    "02054": ("Пустая таблица составного груза", CSEErrorCategory.VALIDATION),
    "02060": ("Отсутствует доступ к сервису отмены заказов", CSEErrorCategory.AUTH),
    "02061": ("Для выбранной географии сервис «Согласованная дата доставки» не осуществляется", CSEErrorCategory.NOT_FOUND),
    "02062": ("Выбранный населённый пункт отправителя не обслуживается", CSEErrorCategory.NOT_FOUND),

    # ── 03xxx: authorisation & authentication ────────────────────────────
    "03010": ("Ошибка авторизации доступа к базе (неверный логин или пароль)", CSEErrorCategory.AUTH),
    "03020": ("Отсутствует информация по правам доступа", CSEErrorCategory.AUTH),
    "03030": ("Нарушение прав доступа", CSEErrorCategory.AUTH),
    "03040": ("По договору заблокировано выполнение операций", CSEErrorCategory.AUTH),
    "03041": ("У клиента не определён основной договор", CSEErrorCategory.AUTH),
    "03050": ("Документ нельзя изменить", CSEErrorCategory.AUTH),
    "03060": ("Изменение пароля запрещено", CSEErrorCategory.AUTH),
    "03061": ("Изменение пароля возможно только при входе с административным паролем", CSEErrorCategory.AUTH),

    # ── 04xxx: document lookup ───────────────────────────────────────────
    "04010": ("Не указан номер документа", CSEErrorCategory.VALIDATION),
    "04011": ("Неверный формат номера документа (должен быть 20 символов с префиксом клиента)", CSEErrorCategory.VALIDATION),
    "04012": ("Не указан номер упаковки", CSEErrorCategory.VALIDATION),
    "04020": ("Не найден такой документ в базе", CSEErrorCategory.NOT_FOUND),
    "04030": ("Номер документа уже используется", CSEErrorCategory.NOT_FOUND),
    "04031": ("Номер упаковки уже используется", CSEErrorCategory.NOT_FOUND),
    "04032": ("Клиентский номер (ClientNumber) уже используется", CSEErrorCategory.NOT_FOUND),
    "04040": ("Документ принадлежит другому клиенту", CSEErrorCategory.AUTH),
    "04050": ("Не указан выгружаемый справочник", CSEErrorCategory.REQUEST_PARAMS),
    "04051": ("Неверно указан выгружаемый справочник", CSEErrorCategory.REQUEST_PARAMS),
    "04060": ("Не указан загружаемый справочник", CSEErrorCategory.REQUEST_PARAMS),
    "04061": ("Неверно указан загружаемый справочник", CSEErrorCategory.REQUEST_PARAMS),
    "04070": ("Некорректный код группы", CSEErrorCategory.VALIDATION),

    # ── 05xxx: field-level validation ────────────────────────────────────
    "05010": ("Не указана срочность", CSEErrorCategory.VALIDATION),
    "05011": ("Срочность заполнена некорректно — используйте срочность в соответствии с договором", CSEErrorCategory.VALIDATION),
    "05020": ("Не указана услуга", CSEErrorCategory.VALIDATION),
    "05021": ("Некорректный код услуги", CSEErrorCategory.VALIDATION),
    "05022": ("Страхование недоступно — услуга не предусмотрена договором", CSEErrorCategory.AUTH),
    "05023": ("Не указана страховая стоимость груза", CSEErrorCategory.VALIDATION),
    "05024": ("Объявленная стоимость недоступна — услуга не предусмотрена договором", CSEErrorCategory.AUTH),
    "05025": ("Не указана объявленная стоимость груза", CSEErrorCategory.VALIDATION),
    "05026": ("Не указана сумма, которую необходимо взять с получателя (COD)", CSEErrorCategory.VALIDATION),
    "05027": ("Некорректный код валюты", CSEErrorCategory.VALIDATION),
    "05028": ("Объявленная стоимость груза превышает максимальную сумму", CSEErrorCategory.VALIDATION),
    "05029": ("Страховая стоимость груза превышает максимальную сумму", CSEErrorCategory.VALIDATION),
    "05030": ("Не указан вид груза", CSEErrorCategory.VALIDATION),
    "05031": ("Некорректный код вида груза", CSEErrorCategory.VALIDATION),
    "05040": ("Не указана география отправителя", CSEErrorCategory.VALIDATION),
    "05041": ("Некорректный код географии отправителя", CSEErrorCategory.VALIDATION),
    "05042": ("Указан некорректный код географии", CSEErrorCategory.VALIDATION),
    "05050": ("Не указана география получателя", CSEErrorCategory.VALIDATION),
    "05051": ("Некорректный код географии получателя", CSEErrorCategory.VALIDATION),
    "05060": ("Не указано контактное лицо", CSEErrorCategory.VALIDATION),
    "05061": ("Некорректный код контактного лица", CSEErrorCategory.VALIDATION),
    "05062": ("По условиям договора необходимо указать контактное лицо", CSEErrorCategory.VALIDATION),
    "05063": ("Не указано контактное лицо отправителя", CSEErrorCategory.VALIDATION),
    "05064": ("Не указано контактное лицо получателя", CSEErrorCategory.VALIDATION),
    "05066": ("Заказ не может быть размещён: вес превышает установленное ограничение", CSEErrorCategory.VALIDATION),
    "05070": ("Не указан офис", CSEErrorCategory.VALIDATION),
    "05071": ("Некорректный код офиса", CSEErrorCategory.VALIDATION),
    "05080": ("Не указано подразделение", CSEErrorCategory.VALIDATION),
    "05081": ("Некорректный код подразделения", CSEErrorCategory.VALIDATION),
    "05082": ("По условиям договора необходимо указать подразделение", CSEErrorCategory.VALIDATION),
    "05083": ("По условиям договора необходимо указать подразделение только из списка предопределённых", CSEErrorCategory.VALIDATION),
    "05090": ("Не указан проект", CSEErrorCategory.VALIDATION),
    "05091": ("Некорректный код проекта", CSEErrorCategory.VALIDATION),
    "05092": ("По условиям договора необходимо указать проект", CSEErrorCategory.VALIDATION),
    "05093": ("По условиям договора номер клиента (ClientNumber) обязателен для заполнения", CSEErrorCategory.VALIDATION),
    "05098": ("Указан некорректный код пункта выдачи заказов (ПВЗ)", CSEErrorCategory.VALIDATION),
    "05099": ("Выбранный ПВЗ не используется или помечен на удаление", CSEErrorCategory.VALIDATION),
    "05100": ("Не указан отправитель", CSEErrorCategory.VALIDATION),
    "05101": ("Некорректный код отправителя", CSEErrorCategory.VALIDATION),
    "05102": ("Указан некорректный дополнительный код клиента", CSEErrorCategory.VALIDATION),
    "05103": ("Необходимо передать другую дату забора для данного региона", CSEErrorCategory.VALIDATION),
    "05104": ("Некорректная дата забора груза", CSEErrorCategory.VALIDATION),
    "05105": ("Некорректная дата доставки груза — получить список доступных дат можно через GetReferenceData:AvailableDeliveryDates", CSEErrorCategory.VALIDATION),
    "05106": ("Некорректное время забора груза", CSEErrorCategory.VALIDATION),
    "05107": ("Не заполнена дата забора груза", CSEErrorCategory.VALIDATION),
    "05110": ("Не указан получатель", CSEErrorCategory.VALIDATION),
    "05111": ("Некорректный код получателя", CSEErrorCategory.VALIDATION),
    "05120": ("Не указан адрес", CSEErrorCategory.VALIDATION),
    "05121": ("Не указан адрес забора", CSEErrorCategory.VALIDATION),
    "05122": ("Не указан адрес доставки", CSEErrorCategory.VALIDATION),
    "05130": ("Не указан телефон", CSEErrorCategory.VALIDATION),
    "05131": ("Не указан телефон отправителя", CSEErrorCategory.VALIDATION),
    "05132": ("Не указан телефон получателя", CSEErrorCategory.VALIDATION),
    "05140": ("Не указан адрес электронной почты", CSEErrorCategory.VALIDATION),
    "05141": ("Не указан адрес электронной почты отправителя", CSEErrorCategory.VALIDATION),
    "05142": ("Не указан адрес электронной почты получателя", CSEErrorCategory.VALIDATION),
    "05143": ("Некорректно заполнен Email для уведомлений (формат: имя@сервер)", CSEErrorCategory.VALIDATION),
    "05144": ("Некорректно заполнен Email отправителя (формат: имя@сервер)", CSEErrorCategory.VALIDATION),
    "05145": ("Некорректно заполнен Email получателя (формат: имя@сервер)", CSEErrorCategory.VALIDATION),
    "05150": ("Не указан плательщик", CSEErrorCategory.VALIDATION),
    "05151": ("Некорректный код плательщика", CSEErrorCategory.VALIDATION),
    "05152": ("Плательщиком может быть только отправитель или получатель", CSEErrorCategory.VALIDATION),
    "05160": ("Не указан способ оплаты", CSEErrorCategory.VALIDATION),
    "05161": ("Некорректный код способа оплаты", CSEErrorCategory.VALIDATION),
    "05170": ("Не указан способ доставки", CSEErrorCategory.VALIDATION),
    "05171": ("Некорректный код способа доставки (некорректный вид доставки)", CSEErrorCategory.VALIDATION),
    "05180": ("Не указан уникальный код (GUID) документа", CSEErrorCategory.VALIDATION),
    "05181": ("Не указан вид документа", CSEErrorCategory.VALIDATION),
    "05182": ("Некорректный вид документа", CSEErrorCategory.VALIDATION),
    "05183": ("Некорректные данные", CSEErrorCategory.VALIDATION),
    "05190": ("Не указан товар", CSEErrorCategory.VALIDATION),
    "05191": ("Некорректный код товара", CSEErrorCategory.VALIDATION),
    "05192": ("Не указана партия товаров", CSEErrorCategory.VALIDATION),
    "05193": ("Некорректный код партии товаров", CSEErrorCategory.VALIDATION),
    "05194": ("Не указан серийный номер товара", CSEErrorCategory.VALIDATION),
    "05195": ("Некорректный код серийного номера товара (проверьте UseSerialNumbers / UIN)", CSEErrorCategory.VALIDATION),
    "05196": ("Не указана характеристика товара", CSEErrorCategory.VALIDATION),
    "05197": ("Некорректный код характеристики товара", CSEErrorCategory.VALIDATION),
    "05198": ("Не указано действие обработки товаров", CSEErrorCategory.VALIDATION),
    "05199": ("По условиям договора необходимо заполнять описание груза", CSEErrorCategory.VALIDATION),
    "05200": ("Не указана единица измерения", CSEErrorCategory.VALIDATION),
    "05201": ("Некорректный код единицы измерения", CSEErrorCategory.VALIDATION),
    "05202": ("Некорректно указаны весогабаритные характеристики (ВГХ)", CSEErrorCategory.VALIDATION),
    "05210": ("Не указана ставка НДС", CSEErrorCategory.VALIDATION),
    "05211": ("Некорректный код ставки НДС", CSEErrorCategory.VALIDATION),
    "05220": ("Некорректный адрес отправителя", CSEErrorCategory.VALIDATION),
    "05221": ("Некорректный адрес получателя", CSEErrorCategory.VALIDATION),
    "05222": ("Такого банка не найдено в списке существующих", CSEErrorCategory.VALIDATION),
    "05223": ("Некорректно заполнен ИНН/КПП (ИНН = 10 симв., КПП = 9 симв.)", CSEErrorCategory.VALIDATION),
    "05224": ("Для создания грузовых мест необходимо указать номер документа с типом «Waybill»", CSEErrorCategory.VALIDATION),
    "05225": ("Не заполнен индекс отправителя (обязателен для международных отправлений)", CSEErrorCategory.VALIDATION),
    "05226": ("Не заполнен индекс получателя (обязателен для международных отправлений)", CSEErrorCategory.VALIDATION),
    "05227": ("Превышено количество символов в индексе отправителя (макс. 10)", CSEErrorCategory.VALIDATION),
    "05228": ("Превышено количество символов в индексе получателя (макс. 10)", CSEErrorCategory.VALIDATION),
    "05555": ("Для сохранения документа с DescriptionForTheVPDreturn необходимо заполнить услугу в AdditionalServices", CSEErrorCategory.VALIDATION),

    # ── 055xx: list & counterparty properties ────────────────────────────
    "05500": ("Не указан вид получаемого списка документов", CSEErrorCategory.LIST_PROPERTIES),
    "05501": ("Некорректный вид получаемого списка документов", CSEErrorCategory.LIST_PROPERTIES),
    "05510": ("Не указан вид контрагента", CSEErrorCategory.LIST_PROPERTIES),
    "05511": ("Некорректный вид контрагента", CSEErrorCategory.LIST_PROPERTIES),

    # ── 06xxx: print forms & scans ───────────────────────────────────────
    "06000": ("Некорректный вид получаемой формы документа (допустимо: print, image, scan)", CSEErrorCategory.PRINT_FORM),
    "06010": ("Печатная форма не найдена (проверьте Name/DocumentType в GetFormsForDocuments)", CSEErrorCategory.PRINT_FORM),
    "06020": ("Не удалось сформировать печатную форму", CSEErrorCategory.PRINT_FORM),
    "06030": ("Скан документа недоступен", CSEErrorCategory.PRINT_FORM),

    # ── 07xxx: e-commerce ────────────────────────────────────────────────
    "07000": ("Контрагент не является интернет-магазином", CSEErrorCategory.ECOM),
    "07010": ("Некорректный код партнёра, выполняющего доставку", CSEErrorCategory.ECOM),
    "07011": ("Клиент не работает с этим партнёром", CSEErrorCategory.ECOM),

    # ── 08xxx: state change log ──────────────────────────────────────────
    "08010": ("Отключена регистрация изменений состояний документов", CSEErrorCategory.STATE_LOG),
    "08011": ("Нельзя удалить запись изменений, по которой не было запроса информации", CSEErrorCategory.STATE_LOG),

    # ── other / catch-all ────────────────────────────────────────────────
    "10010": ("Некорректный формат файла", CSEErrorCategory.OTHER),
    "10020": ("Некорректный код ошибки", CSEErrorCategory.OTHER),
    "99010": ("Неизвестная ошибка", CSEErrorCategory.OTHER),
}


def describe(code: str) -> str:
    """Return the human-readable message for a CSE error code.

    Falls back to a generic label when the code is not in the registry — CSE
    occasionally emits codes that are not documented in the current PDF, in
    which case we still surface the raw code so support can look it up.
    """
    entry = _ERROR_CODE_MAP.get(code)
    if entry is None:
        return f"неизвестный код КСЭ ({code})" if code else "неизвестная ошибка КСЭ"
    return entry[0]


def category(code: str) -> CSEErrorCategory:
    """Return the CSEErrorCategory for a code (OTHER when unknown)."""
    entry = _ERROR_CODE_MAP.get(code)
    return entry[1] if entry is not None else CSEErrorCategory.OTHER


def format_error(method: str, code: str, extra: str | None = None) -> str:
    """Build a canonical error message string for RuntimeError.

    Format: 'CSE {method} error [{code}]: {description}[; {extra}]'
    """
    parts = [f"CSE {method} error"]
    if code:
        parts[0] += f" [{code}]"
    parts.append(describe(code))
    if extra:
        parts.append(extra)
    return ": ".join(parts[:2]) + (f"; {extra}" if extra else "")


# ---------------------------------------------------------------------------
# Freeform text errors for SaveWaybillOffice (no numeric code)
# ---------------------------------------------------------------------------
#
# Per PDF page 7 «Список ошибок для функции SaveWaybillOffice» — these come
# back inside <m:ErrorInfo> as plain Russian text. We match on stable substrings
# and normalise into structured hints so calling code can surface product-level
# problems (row number, offending UIN) without regex-parsing at each callsite.

SAVE_WAYBILL_OFFICE_TEXT_MARKERS: tuple[tuple[str, str], ...] = (
    ("Некорректный формат даты", "invalid_datetime"),
    ("может быть передано только одно значение", "serial_or_uin_conflict"),
    ("Для ювелирной продукции может быть передан только", "jewellery_uin_only"),
    ("UIN можно передавать только для ювелирной продукции", "uin_non_jewellery"),
    ("некорректный уникальный идентификатор", "invalid_uin"),
    ("UIN принадлежит другому товару", "uin_wrong_product"),
)


# ---------------------------------------------------------------------------
# UpdateClientProducts freeform errors (kept for future товарной накладной)
# ---------------------------------------------------------------------------
UPDATE_CLIENT_PRODUCTS_TEXT_MARKERS: tuple[tuple[str, str], ...] = (
    ("Некорректный код товара", "invalid_product_code"),
    ("Максимальное количество символов в поле Наименование", "name_too_long"),
    ("Параметр Наименование не заполнен", "missing_name"),
    ("Не найден тип товара в базе", "unknown_product_type"),
    ("не указан поставщик", "missing_supplier"),
    ("Не найден поставщик товара", "unknown_supplier"),
    ("Не корректный телефон", "invalid_supplier_phone"),
    ("Нет прав доступа для создания новых товаров", "no_create_permission"),
    ("Максимальное количество символов в поле Артикул", "article_too_long"),
    ("Параметр Единица Измерения не заполнен", "missing_unit"),
    ("Не удалось найти Единицу Измерения", "unknown_unit"),
    ("Не найдена ставка НДС", "unknown_vat"),
    ("Ставка 0% в товарах не используется", "invalid_vat_zero"),
    ("Не найден проект в базе", "unknown_project"),
    ("Нет прав доступа для изменения существующих товаров", "no_update_permission"),
    ("Не найден тип маркировки товара", "unknown_marking_type"),
    ("Отключён учёт по серийным номерам", "serial_tracking_disabled"),
    ("Серийный номер с таким названием уже существует", "duplicate_serial"),
    ("Данный УИН уже зарегистрирован в системе", "duplicate_uin"),
    ("Для ювелирной продукции необходимо передавать только УИН", "jewellery_uin_required"),
    ("Некорректный код географии", "invalid_geography"),
)


def classify_freeform_error(text: str, markers: tuple[tuple[str, str], ...]) -> str | None:
    """Return the marker slug for the first substring that appears in ``text``,
    or ``None`` if nothing matches. Case-insensitive."""
    if not text:
        return None
    haystack = text.lower()
    for needle, slug in markers:
        if needle.lower() in haystack:
            return slug
    return None


# ---------------------------------------------------------------------------
# Structured exception for SaveWaybillOffice validation
# ---------------------------------------------------------------------------

# Row references appear as "в строке: [12]" / "в строке: 5" / "строка 3".
# CSE syntax is a bit loose — cover the common shapes.
import re as _re

_ROW_RE = _re.compile(
    r"в\s+строке\s*[:\-]?\s*\[?\s*(\d+)\s*\]?"
    r"|строк[аеи]\s*(\d+)",
    _re.IGNORECASE,
)
_UIN_RE = _re.compile(r"UIN[»\"\s]*[:\-]?\s*[»\"]?\s*([A-Za-z0-9\-]{6,})", _re.IGNORECASE)


class CSEWaybillValidationError(RuntimeError):
    """SaveWaybillOffice-specific validation error with structured attributes.

    Attributes:
        code — numeric CSE code if the failure came back with one (else '').
        message — human-readable description.
        slug — freeform-marker slug (see SAVE_WAYBILL_OFFICE_TEXT_MARKERS), if
               the ErrorInfo text matched a known pattern. None otherwise.
        product_row — 1-based index of the offending Products row (if the text
                      referenced one).
        offending_value — extracted UIN / SerialNumber / value the API said was
                          wrong; empty when the text does not mention one.
        raw_info — full ErrorInfo text as returned by CSE (for logging).
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        slug: str | None = None,
        product_row: int | None = None,
        offending_value: str = "",
        raw_info: str = "",
    ):
        parts = ["CSE SaveWaybillOffice error"]
        if code:
            parts[0] += f" [{code}]"
        parts.append(message)
        summary = ": ".join(parts)
        extras: list[str] = []
        if product_row is not None:
            extras.append(f"row={product_row}")
        if offending_value:
            extras.append(f"value={offending_value}")
        if extras:
            summary = f"{summary}; {'; '.join(extras)}"
        super().__init__(summary)
        self.code = code
        self.message = message
        self.slug = slug
        self.product_row = product_row
        self.offending_value = offending_value
        self.raw_info = raw_info


def parse_save_waybill_error(code: str, info: str) -> CSEWaybillValidationError:
    """Turn a CSE SaveWaybillOffice failure into a structured exception.

    ``code`` — numeric CSE code from Description (may be empty for freeform
        text-only errors).
    ``info`` — ErrorInfo text (may be empty for numeric-only errors).
    """
    slug = classify_freeform_error(info, SAVE_WAYBILL_OFFICE_TEXT_MARKERS)

    row: int | None = None
    m = _ROW_RE.search(info or "")
    if m:
        row_str = m.group(1) or m.group(2)
        try:
            row = int(row_str)
        except (ValueError, TypeError):
            row = None

    offending_value = ""
    m = _UIN_RE.search(info or "")
    if m:
        offending_value = m.group(1)

    # Prefer the code-driven description when a numeric code came back;
    # otherwise use the ErrorInfo text so freeform errors still carry meaning.
    message = describe(code) if code else (info or "неизвестная ошибка")

    return CSEWaybillValidationError(
        code=code,
        message=message,
        slug=slug,
        product_row=row,
        offending_value=offending_value,
        raw_info=info or "",
    )
