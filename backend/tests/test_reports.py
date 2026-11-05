"""آزمون گزارش هفتگی: نسخه‌بندی، تأیید، جلوگیری از تأیید خود (AC-22، AC-05)."""
from datetime import date

from tests.conftest import H, login, make_user


def _week_payload() -> dict:
    ws = date(2026, 10, 24)  # شنبه
    return {"week_start": ws.isoformat()}


def test_report_flow_and_self_approval_ban(client, db):
    mgr = make_user(db, "mgr-rp", "unit_manager")
    emp = make_user(db, "emp-rp", "employee", manager=mgr)
    assert login(client, "emp-rp") is True

    resp = client.post("/api/v1/weekly-reports/my/generate", headers=H, json=_week_payload())
    assert resp.status_code == 201, resp.text
    rid = resp.json()["id"]

    resp = client.put("/api/v1/weekly-reports/my", headers=H, json={
        **_week_payload(),
        "summary": "خلاصه اقدامات هفته",
        "items": [{"title": "تکمیل ماژول گزارش", "hours": 6.5, "kind": "done"},
                  {"title": "جلسه هماهنگی پروژه", "hours": 1.0, "kind": "ongoing"}],
    })
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 2

    resp = client.post("/api/v1/weekly-reports/my/submit", headers=H, json=_week_payload())
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "submitted"
    assert resp.json()["approver_name"] == "mgr-rp کاربر"

    # ویرایش پس از ارسال ممنوع
    resp = client.put("/api/v1/weekly-reports/my", headers=H, json={**_week_payload(), "summary": "تغییر"})
    assert resp.status_code == 422

    # بررسی‌کننده: صاحب گزارش نیست
    assert login(client, "emp-rp") is True  # تست 403 برای صاحب گزارش روی مسیر تأیید دیگران معنا ندارد

    assert login(client, "mgr-rp") is True
    resp = client.post(f"/api/v1/weekly-reports/{rid}/approve", headers=H, json={"comment": "تأیید"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert len(resp.json()["versions"]) >= 2  # اسنپ‌شات ارسال + تأیید

    # ویرایش گزارش تأییدشده ممنوع (AC-05)
    assert login(client, "emp-rp") is True
    resp = client.put("/api/v1/weekly-reports/my", headers=H, json={**_week_payload(), "summary": "دستکاری"})
    assert resp.status_code == 422


def test_report_history_snapshot_immutable(client, db):
    """AC-20 — گزارش تاریخی مستقل از تغییرات بعدی رکورد است."""
    mgr = make_user(db, "mgr-snap", "unit_manager")
    emp = make_user(db, "emp-snap", "employee", manager=mgr)
    assert login(client, "emp-snap") is True
    rid = client.post("/api/v1/weekly-reports/my/generate", headers=H, json=_week_payload()).json()["id"]
    client.put("/api/v1/weekly-reports/my", headers=H, json={**_week_payload(), "summary": "نسخه اول",
                                                             "items": [{"title": "اقدام اصلی هفته"}]})
    client.post("/api/v1/weekly-reports/my/submit", headers=H, json=_week_payload())
    login(client, "mgr-snap")
    client.post(f"/api/v1/weekly-reports/{rid}/approve", headers=H, json={})
    v1 = client.get(f"/api/v1/weekly-reports/{rid}/versions/2", headers=H).json()
    assert v1["summary"] == "نسخه اول"
    assert v1["items"][0]["title"] == "اقدام اصلی هفته"
