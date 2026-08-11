"""XLSX builder for admin/carrier exports.

Design notes:
- Uses the normal (non-write-only) `Workbook` so we can measure actual cell
  widths and auto-fit column widths from data. write_only would be marginally
  cheaper in RAM but blocks auto-width — with MAX_EXPORT_ROWS = 50k the memory
  cost is under 100 MB, acceptable trade for professional-looking output.
- Header uses a light "cloud" background with dark navy text — earlier the
  navy fill was too heavy visually and hurt readability under printed output.
- Accounting number format for money makes negatives red automatically — useful
  for commission reversals ("возврат" rows come through as negative amounts).
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Iterable
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.child import INVALID_TITLE_REGEX

# Hard cap on rows per export. 50k covers a full month of orders comfortably;
# larger exports should be split by period or exported async (out of scope).
MAX_EXPORT_ROWS = 50_000

# Excel accounting format: normal positive, red negative with minus sign.
# The trailing space aligns columns visually when values are of varying widths.
MONEY_FORMAT = '#,##0.00_ ;[Red]-#,##0.00 '
DATE_FORMAT = "DD.MM.YYYY"
DATETIME_FORMAT = "DD.MM.YYYY HH:MM"

# Light header: cloud background + navy bold text. Original navy fill was too
# heavy — hard to read black text on it, and printed exports lost detail.
_HEADER_FILL = PatternFill("solid", fgColor="F1F5F9")
_HEADER_FONT = Font(bold=True, color="0B2545", size=11)
_HEADER_BORDER = Border(bottom=Side(border_style="medium", color="0B2545"))
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)

_TOTAL_FONT = Font(bold=True, size=11, color="0B2545")
_TOTAL_FILL = PatternFill("solid", fgColor="F1F5F9")
_TOTAL_BORDER = Border(top=Side(border_style="medium", color="0B2545"))

# Auto-width heuristic: multiplier per character + padding, then clamp.
_WIDTH_MIN = 8
_WIDTH_MAX = 60
_WIDTH_PADDING = 2  # extra chars beyond longest value in the column


def _safe_sheet_name(name: str) -> str:
    # Excel sheet names ≤ 31 chars, no []:*?/\.
    cleaned = INVALID_TITLE_REGEX.sub(" ", name).strip()
    return (cleaned or "Sheet")[:31]


def _format_filename(base: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    return f"{base}_{stamp}.xlsx"


def _display_length(val, is_money: bool, is_date: bool, is_datetime: bool) -> int:
    """Approximate width in characters this cell will take once formatted.

    Cyrillic renders wider than pure ASCII in most fonts — we bump those chars
    slightly so columns like «Адрес получателя» don't get chopped.
    """
    if val is None:
        return 0
    if is_money:
        # "1 234 567.89" ≈ 12 chars for a big amount; empirically ~length of
        # str + 3 for thousands separators and decimal padding.
        try:
            return len(f"{float(val):,.2f}") + 1
        except (TypeError, ValueError):
            return 0
    if is_date:
        return 10  # DD.MM.YYYY
    if is_datetime:
        return 16  # DD.MM.YYYY HH:MM
    s = str(val)
    # Cyrillic weighs slightly more than ASCII in most sans-serif fonts.
    cyr = sum(1 for ch in s if "Ѐ" <= ch <= "ӿ")
    return len(s) + int(cyr * 0.15)


def build_xlsx_response(
    *,
    filename_base: str,
    sheet_name: str,
    headers: list[str],
    rows: Iterable[list],
    money_cols: list[int] | None = None,
    date_cols: list[int] | None = None,
    datetime_cols: list[int] | None = None,
    total_row: list | None = None,
    col_widths: list[int] | None = None,
) -> StreamingResponse:
    """Build an XLSX file and stream it back to the client.

    Args:
        filename_base: filename without extension or timestamp (e.g. "orders_admin").
            Timestamp and .xlsx suffix are appended automatically.
        sheet_name: displayed sheet tab name (auto-sanitised for Excel rules).
        headers: column titles, one per column.
        rows: iterable of row-lists. Enforces MAX_EXPORT_ROWS.
        money_cols: 1-based column indexes to format as accounting (money).
        date_cols: 1-based column indexes to format as date (DD.MM.YYYY).
        datetime_cols: 1-based column indexes to format as datetime.
        total_row: optional totals row appended at the bottom, bold + cloud bg.
        col_widths: optional per-column widths (Excel char-units). If omitted,
            widths are auto-calculated from the longest value in each column
            (clamped between _WIDTH_MIN and _WIDTH_MAX).
    """
    money_set = set(money_cols or [])
    date_set = set(date_cols or [])
    datetime_set = set(datetime_cols or [])

    # Materialise rows once — we need to iterate twice (write cells + measure
    # widths). MAX_EXPORT_ROWS cap makes this safe memory-wise (~100 MB peak
    # even for wide tables at 50k rows).
    rows_list: list[list] = []
    for row in rows:
        if len(rows_list) >= MAX_EXPORT_ROWS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Слишком много данных для экспорта (>{MAX_EXPORT_ROWS} строк). "
                    "Сузьте фильтры (например, укажите период)."
                ),
            )
        rows_list.append(row)

    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(sheet_name)

    # ── Header row ──────────────────────────────────────────────────────────
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _HEADER_ALIGN
        cell.border = _HEADER_BORDER
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"

    # ── Data rows ───────────────────────────────────────────────────────────
    for row in rows_list:
        # Money cells: force float so openpyxl serialises correctly (Decimal
        # gets written as string otherwise). None → empty cell.
        row_values = [
            (float(v) if v is not None and (i + 1) in money_set else v)
            for i, v in enumerate(row)
        ]
        ws.append(row_values)

    # Apply number formats. Iterating from row 2 (data starts) to end (or
    # end-1 if we'll add a total row — set after).
    last_data_row = 1 + len(rows_list)
    for col_idx in range(1, len(headers) + 1):
        if col_idx in money_set:
            fmt = MONEY_FORMAT
        elif col_idx in date_set:
            fmt = DATE_FORMAT
        elif col_idx in datetime_set:
            fmt = DATETIME_FORMAT
        else:
            continue
        for row_idx in range(2, last_data_row + 1):
            ws.cell(row=row_idx, column=col_idx).number_format = fmt

    # ── Total row ───────────────────────────────────────────────────────────
    if total_row is not None:
        row_values = [
            (float(v) if v is not None and (i + 1) in money_set else v)
            for i, v in enumerate(total_row)
        ]
        ws.append(row_values)
        total_row_idx = last_data_row + 1
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=total_row_idx, column=col_idx)
            cell.font = _TOTAL_FONT
            cell.fill = _TOTAL_FILL
            cell.border = _TOTAL_BORDER
            if col_idx in money_set:
                cell.number_format = MONEY_FORMAT
            elif col_idx in date_set:
                cell.number_format = DATE_FORMAT
            elif col_idx in datetime_set:
                cell.number_format = DATETIME_FORMAT

    # ── Column widths ───────────────────────────────────────────────────────
    if col_widths:
        # Explicit widths take precedence — respect the endpoint's guidance
        # (e.g. for wide address/note columns where auto-width overshoots).
        for idx, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width
    else:
        # Auto-width: max of (header length, longest data value) + padding,
        # clamped to keep pathological rows from creating 300-char columns.
        for col_idx in range(1, len(headers) + 1):
            is_money = col_idx in money_set
            is_date = col_idx in date_set
            is_dt = col_idx in datetime_set
            max_len = _display_length(headers[col_idx - 1], False, False, False)
            for row in rows_list:
                if col_idx - 1 < len(row):
                    max_len = max(
                        max_len,
                        _display_length(row[col_idx - 1], is_money, is_date, is_dt),
                    )
            if total_row and col_idx - 1 < len(total_row):
                max_len = max(
                    max_len,
                    _display_length(total_row[col_idx - 1], is_money, is_date, is_dt),
                )
            width = max(_WIDTH_MIN, min(_WIDTH_MAX, max_len + _WIDTH_PADDING))
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Save & stream ───────────────────────────────────────────────────────
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = _format_filename(filename_base)
    disposition = (
        f'attachment; filename="{filename}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": disposition},
    )


def fmt_dt(dt: datetime | None) -> datetime | None:
    """Pass datetime through as-is (openpyxl formats it via number_format)."""
    return dt


def fmt_date(d: date | datetime | None) -> date | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    return d
