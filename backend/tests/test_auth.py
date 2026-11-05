"""آزمون احراز هویت و کنترل دسترسی (AC-01)."""
from tests.conftest import H, login, make_user


def test_login_success_and_me(client, db):
    make_user(db, "alice", "employee")
    assert login(client, "alice") is True
    resp = client.get("/api/v1/auth/me", headers=H)
    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == "alice"
    assert "employee" in resp.json()["user"]["roles"]


def test_login_wrong_password(client, db):
    make_user(db, "bob", "employee")
    resp = client.post("/api/v1/auth/login", json={"username": "bob", "password": "wrong-pass"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 401


def test_login_lockout_after_failures(client, db):
    make_user(db, "carol", "employee")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "carol", "password": "wrong-pass"},
                    headers={"X-Requested-With": "XMLHttpRequest"})
    resp = client.post("/api/v1/auth/login", json={"username": "carol", "password": "Test@1234"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 423  # قفل موقت


def test_csrf_required(client, db):
    make_user(db, "dave", "employee")
    resp = client.post("/api/v1/auth/login", json={"username": "dave", "password": "Test@1234"})
    assert resp.status_code == 403  # بدون سربرگ X-Requested-With


def test_unauthorized_access(client):
    resp = client.get("/api/v1/tasks", headers=H)
    assert resp.status_code == 401


def test_direct_access_to_forbidden_record(client, db):
    """AC-01 — درخواست مستقیم رکورد غیرمجاز ⇒ رد دسترسی."""
    e1 = make_user(db, "emp-a1", "employee")
    e2 = make_user(db, "emp-a2", "employee")
    from app.models.task import Task
    from app.models.enums import TaskStatus

    t = Task(code="T-AC01", title="وظیفه خصوصی کاربر اول", assignee_id=e1.id, created_by=e1.id,
             status=TaskStatus.assigned)
    db.add(t)
    db.flush()
    db.commit()  # برای دیده‌شدن در نشست API

    assert login(client, "emp-a2") is True
    resp = client.get(f"/api/v1/tasks/{t.id}", headers=H)
    assert resp.status_code == 404  # وجود رکورد افشا نمی‌شود

    assert login(client, "emp-a1") is True
    resp = client.get(f"/api/v1/tasks/{t.id}", headers=H)
    assert resp.status_code == 200
