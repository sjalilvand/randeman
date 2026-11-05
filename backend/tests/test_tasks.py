"""آزمون گردش کار وظایف (سند ۵.۳)."""
from tests.conftest import H, login, make_user


def _create_task(client, db, assignee_id: str) -> dict:
    resp = client.post("/api/v1/tasks", headers=H, json={
        "title": "تهیه گزارش آزمون", "assignee_id": assignee_id,
        "base_due_date": "2026-12-01", "current_due_date": "2026-12-01",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_full_workflow(client, db):
    mgr = make_user(db, "mgr-wf", "unit_manager")
    emp = make_user(db, "emp-wf", "employee", manager=mgr)
    assert login(client, "mgr-wf") is True
    task = _create_task(client, db, str(emp.id))
    tid = task["id"]
    assert task["status"] == "assigned"

    # ارسال خروجی بدون یادداشت ممنوع
    assert login(client, "emp-wf") is True
    resp = client.post(f"/api/v1/tasks/{tid}/submit-for-review", headers=H, json={})
    assert resp.status_code == 422

    # شروع و ارسال توسط مسئول
    assert client.post(f"/api/v1/tasks/{tid}/start", headers=H).json()["status"] == "in_progress"
    resp = client.post(f"/api/v1/tasks/{tid}/submit-for-review", headers=H,
                       json={"delivery_note": "خروجی نهایی با شواهد پیوست شده است"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready_for_review"

    # کارمند نمی‌تواند خودش تأیید کند
    assert login(client, "emp-wf") is True
    resp = client.post(f"/api/v1/tasks/{tid}/approve", headers=H, json={})
    assert resp.status_code == 403

    # مدیر مجاز تأیید می‌کند
    assert login(client, "mgr-wf") is True
    resp = client.post(f"/api/v1/tasks/{tid}/approve", headers=H, json={"comment": "تأیید شد"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["progress"] == 100

    # بازگشایی نیازمند دلیل
    resp = client.post(f"/api/v1/tasks/{tid}/reopen", headers=H, json={"reason": "بازگشایی با مجوز — نقص کشف شد"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_invalid_transition_rejected(client, db):
    emp = make_user(db, "emp-tr", "employee")
    assert login(client, "emp-tr") is True
    resp = client.post("/api/v1/tasks", headers=H, json={
        "title": "وظیفه انتقال نامعتبر", "assignee_id": str(emp.id),
    })
    tid = resp.json()["id"]
    # از assigned مستقیم به آماده بررسی مجاز نیست
    resp = client.post(f"/api/v1/tasks/{tid}/submit-for-review", headers=H,
                       json={"delivery_note": "ارسال مستقیم بدون شروع"})
    assert resp.status_code == 422


def test_due_change_request_flow(client, db):
    mgr = make_user(db, "mgr-dc", "unit_manager")
    emp = make_user(db, "emp-dc", "employee", manager=mgr)
    assert login(client, "mgr-dc") is True
    task = _create_task(client, db, str(emp.id))
    tid = task["id"]

    assert login(client, "emp-dc") is True
    resp = client.post(f"/api/v1/tasks/{tid}/request-due-date-change", headers=H,
                       json={"new_due_date": "2026-12-15", "reason": "وابستگی به تأمین سخت‌افزار"})
    assert resp.status_code == 201

    assert login(client, "mgr-dc") is True
    cr_id = resp_id = None
    detail = client.get(f"/api/v1/tasks/{tid}", headers=H).json()
    cr = detail["change_requests"][0]
    resp = client.post(f"/api/v1/tasks/{tid}/due-change-requests/{cr['id']}/decide", headers=H,
                       json={"approve": True, "comment": "موافقت با ثبت تاریخچه"})
    assert resp.status_code == 200
    detail = client.get(f"/api/v1/tasks/{tid}", headers=H).json()
    assert detail["current_due_date"] == "2026-12-15"
    assert detail["base_due_date"] == "2026-12-01"  # سررسید مبنا حفظ می‌شود


def test_cycle_dependency_rejected(client, db):
    emp = make_user(db, "emp-dep", "employee")
    assert login(client, "emp-dep") is True
    t1 = client.post("/api/v1/tasks", headers=H, json={"title": "وظیفه یک", "assignee_id": str(emp.id)}).json()
    t2 = client.post("/api/v1/tasks", headers=H, json={"title": "وظیفه دو", "assignee_id": str(emp.id)}).json()
    assert client.post(f"/api/v1/tasks/{t2['id']}/dependencies", headers=H,
                       json={"depends_on_task_id": t1["id"]}).status_code == 201
    # چرخه: t1 به t2 وابسته شود ⇒ رد
    resp = client.post(f"/api/v1/tasks/{t1['id']}/dependencies", headers=H,
                       json={"depends_on_task_id": t2["id"]})
    assert resp.status_code == 422
