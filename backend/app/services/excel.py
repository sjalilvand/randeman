"""خروجی Excel با openpyxl — پیشگیری از تزریق فرمول (سند ۱۲.۴، AC-12)."""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.core.config import settings
import jdatetime

_HEADER_FILL = PatternFill("solid", fgColor="0F766E")
_HEADER_FONT = Font(color="FFFFFF", bold=True, name="Vazirmatn", size=11)


def safe_cell(value: Any) -> Any:
    """جلوگیری از اجرای فرمول در متن خروجی."""
    if isinstance(value, str) and value[:1] in ("=", "+", "@") or (isinstance(value, str) and value.startswith("-") and len(value) > 1 and not _is_number(value)):
        return "'" + value
    return value


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def jdate_str(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    return jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")


def build_workbook(
    *,
    title: str,
    period_label: str | None,
    filters_label: str | None,
    columns: list[str],
    rows: list[list[Any]],
    generated_by: str,
) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = (title or "گزارش")[:31]
    ws.rightToLeft = True

    ws.cell(row=1, column=1, value=f"{settings.app_name} — {title}").font = Font(bold=True, size=13, name="Vazirmatn")
    info_row = 2
    ws.cell(row=info_row, column=1, value=f"بازه: {period_label or '—'}")
    ws.cell(row=info_row, column=2, value=f"فیلترها: {filters_label or '—'}")
    ws.cell(row=info_row, column=3, value=f"تولیدکننده: {generated_by}")
    ws.cell(row=info_row, column=4, value=f"زمان تولید: {jdate_str(datetime.now())} {datetime.now().strftime('%H:%M')}")

    header_row = 4
    for col, name in enumerate(columns, start=1):
        c = ws.cell(row=header_row, column=col, value=name)
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
        c.alignment = Alignment(horizontal="center")

    for r, row in enumerate(rows, start=header_row + 1):
        for c, value in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=safe_cell(value))

    for col_idx, _name in enumerate(columns, start=1):
        ws.column_dimensions[ws.cell(row=header_row, column=col_idx).column_letter].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
