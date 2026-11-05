"""آزمون خروجی Excel: عدم اجرای فرمول (AC-12)."""
from app.services.excel import build_workbook, safe_cell


def test_formula_injection_guard():
    assert safe_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert safe_cell("+cmd") == "'+cmd"
    assert safe_cell("@risk") == "'@risk"
    assert safe_cell("متن معمولی") == "متن معمولی"
    assert safe_cell(42) == 42


def test_workbook_builds():
    buf = build_workbook(
        title="گزارش آزمون", period_label="۱۴۰۵/۰۸/۰۱ تا ۱۴۰۵/۰۸/۰۷",
        filters_label="وضعیت=فعال", columns=["کد", "عنوان"], rows=[["T-1", "=danger"]],
        generated_by="آزمون",
    )
    data = buf.read()
    assert data[:2] == b"PK"  # فایل xlsx معتبر
