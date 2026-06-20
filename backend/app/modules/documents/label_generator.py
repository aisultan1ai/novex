from __future__ import annotations

import os
import platform

try:
    from fpdf import FPDF

    _FPDF_AVAILABLE = True
except ImportError:
    _FPDF_AVAILABLE = False

from app.modules.orders.models import OrderDraft, ShipmentParty


def _find_unicode_font() -> str | None:
    system = platform.system()
    candidates: list[str] = []

    if system == "Windows":
        win_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        candidates = [
            os.path.join(win_fonts, "arial.ttf"),
            os.path.join(win_fonts, "ARIAL.TTF"),
            os.path.join(win_fonts, "calibri.ttf"),
        ]
    elif system == "Darwin":
        candidates = [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _find_unicode_font_bold() -> str | None:
    system = platform.system()
    candidates: list[str] = []

    if system == "Windows":
        win_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
        candidates = [
            os.path.join(win_fonts, "arialbd.ttf"),
            os.path.join(win_fonts, "ARIALBD.TTF"),
            os.path.join(win_fonts, "calibrib.ttf"),
        ]
    elif system == "Darwin":
        candidates = ["/Library/Fonts/Arial Bold.ttf"]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _find_party(order: OrderDraft, role: str) -> ShipmentParty | None:
    for p in order.parties:
        if p.role == role:
            return p
    return None


# Resolved once at import time — filesystem scan is expensive per-request
_FONT_REGULAR: str | None = _find_unicode_font()
_FONT_BOLD: str | None = _find_unicode_font_bold()


def generate_label_pdf(order: OrderDraft) -> bytes:
    if not _FPDF_AVAILABLE:
        raise RuntimeError(
            "Для генерации накладных установите пакет: pip install fpdf2"
        )

    if _FONT_REGULAR is None:
        raise RuntimeError(
            "Не найден Unicode-шрифт для генерации PDF. "
            "Убедитесь, что на сервере установлен Arial или DejaVuSans."
        )

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    pdf.add_font("UniFont", style="", fname=_FONT_REGULAR)
    pdf.add_font("UniFont", style="B", fname=_FONT_BOLD or _FONT_REGULAR)

    def regular(size: int = 10) -> None:
        pdf.set_font("UniFont", style="", size=size)

    def bold(size: int = 10) -> None:
        pdf.set_font("UniFont", style="B", size=size)

    # Header
    bold(18)
    pdf.cell(0, 12, "NOVEX LOGISTICS", new_x="LMARGIN", new_y="NEXT", align="C")
    regular(10)
    pdf.cell(0, 6, "Накладная / Waybill", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Order meta
    def meta_row(label: str, value: str) -> None:
        bold(11)
        pdf.cell(55, 7, label, new_x="RIGHT", new_y="TOP")
        regular(11)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    meta_row("Номер заказа:", f"#{order.id}")
    meta_row("Дата:", order.created_at.strftime("%d.%m.%Y"))
    meta_row("Перевозчик:", order.carrier_name_snapshot)
    meta_row("Тариф:", order.tariff_name_snapshot)
    meta_row(
        "Маршрут:",
        f"{order.from_city_snapshot} ({order.from_country_snapshot})"
        f" → {order.to_city_snapshot} ({order.to_country_snapshot})",
    )
    meta_row(
        "Срок доставки:",
        f"{order.eta_days_min_snapshot}–{order.eta_days_max_snapshot} дней",
    )
    meta_row("Стоимость:", f"{order.price_snapshot} {order.currency_snapshot}")
    pdf.ln(3)

    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Sender / Recipient columns
    sender = _find_party(order, "sender")
    recipient = _find_party(order, "recipient")
    col_w = 90

    bold(12)
    pdf.cell(col_w, 8, "ОТПРАВИТЕЛЬ", new_x="RIGHT", new_y="TOP")
    pdf.cell(0, 8, "ПОЛУЧАТЕЛЬ", new_x="LMARGIN", new_y="NEXT")

    def _party_lines(p: ShipmentParty | None) -> list[str]:
        if p is None:
            return ["—"]
        lines: list[str] = [p.full_name, p.phone]
        if p.company_name:
            lines.append(p.company_name)
        lines.append(f"{p.city}, {p.country}")
        lines.append(p.address_line1)
        if p.address_line2:
            lines.append(p.address_line2)
        return lines

    sender_lines = _party_lines(sender)
    recipient_lines = _party_lines(recipient)
    max_lines = max(len(sender_lines), len(recipient_lines))

    regular(10)
    for i in range(max_lines):
        s_text = sender_lines[i] if i < len(sender_lines) else ""
        r_text = recipient_lines[i] if i < len(recipient_lines) else ""
        pdf.cell(col_w, 6, s_text, new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 6, r_text, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Packages table
    bold(12)
    pdf.cell(0, 8, "ПОСЫЛКИ", new_x="LMARGIN", new_y="NEXT")

    bold(9)
    pdf.cell(60, 6, "Описание", border=1, new_x="RIGHT", new_y="TOP")
    pdf.cell(20, 6, "Кол-во", border=1, align="C", new_x="RIGHT", new_y="TOP")
    pdf.cell(25, 6, "Вес, кг", border=1, align="C", new_x="RIGHT", new_y="TOP")
    pdf.cell(30, 6, "Ш×В×Г, см", border=1, align="C", new_x="RIGHT", new_y="TOP")
    pdf.cell(
        0, 6, "Объявл. ценность", border=1, align="C", new_x="LMARGIN", new_y="NEXT"
    )

    regular(9)
    for pkg in order.packages:
        dims = f"{pkg.width_cm}×{pkg.height_cm}×{pkg.depth_cm}"
        declared = (
            f"{pkg.declared_value} {pkg.declared_value_currency}"
            if pkg.declared_value
            else "—"
        )
        pdf.cell(60, 6, pkg.description[:35], border=1, new_x="RIGHT", new_y="TOP")
        pdf.cell(
            20, 6, str(pkg.quantity), border=1, align="C", new_x="RIGHT", new_y="TOP"
        )
        pdf.cell(
            25, 6, str(pkg.weight_kg), border=1, align="C", new_x="RIGHT", new_y="TOP"
        )
        pdf.cell(30, 6, dims, border=1, align="C", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 6, declared, border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    # Additional services
    services: list[str] = []
    if order.call_before_delivery:
        services.append("Звонок перед доставкой")
    if order.insurance:
        services.append("Страхование")
    if order.fragile:
        services.append("Хрупкий груз")
    if services:
        bold(10)
        pdf.cell(
            0, 7, "Доп. услуги: " + ", ".join(services), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.ln(2)

    # Reference barcode-style footer
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    bold(14)
    pdf.cell(
        0, 10, f"REF: NOVEX-{order.id:08d}", new_x="LMARGIN", new_y="NEXT", align="C"
    )

    return bytes(pdf.output())
