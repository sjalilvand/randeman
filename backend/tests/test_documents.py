"""آزمون مستندات: پسوند ممنوع (AC-08)، قرنطینه بدون ClamAV (AC-16)، کنترل دانلود (AC-07)."""
from tests.conftest import H, login, make_user


def test_executable_extension_rejected(client, db):
    """AC-08 — فایل اجرایی یا اسکریپت رد می‌شود."""
    make_user(db, "doc-emp", "employee")
    assert login(client, "doc-emp") is True
    resp = client.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", b"MZ\x90\x00 binary", "application/octet-stream")},
        data={"title": "فایل ممنوع"},
        headers=H,
    )
    assert resp.status_code == 422


def test_upload_without_clamav_stays_quarantined(client, db):
    """AC-16 — توقف ClamAV ⇒ فایل در قرنطینه می‌ماند و قابل دانلود نیست."""
    make_user(db, "doc-emp2", "employee")
    assert login(client, "doc-emp2") is True
    resp = client.post(
        "/api/v1/documents",
        files={"file": ("report.pdf", b"%PDF-1.7 fake content", "application/pdf")},
        data={"title": "گزارش آزمایشی"},
        headers=H,
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "quarantined"

    # دانلود از قرنطینه ممنوع
    resp = client.get(f"/api/v1/documents/{doc['id']}/download", headers=H)
    assert resp.status_code == 423


def test_document_size_limit(client, db):
    make_user(db, "doc-emp3", "employee")
    assert login(client, "doc-emp3") is True
    big = b"PK\x03\x04" + b"0" * (21 * 1024 * 1024)
    resp = client.post(
        "/api/v1/documents",
        files={"file": ("big.xlsx", big, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"title": "فایل بزرگ"},
        headers=H,
    )
    assert resp.status_code == 422
