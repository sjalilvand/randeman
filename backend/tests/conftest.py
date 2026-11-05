"""کانفیگ آزمون — SQLite ایزوله برای هر نشست pytest."""
from __future__ import annotations

import os
import tempfile

import pytest

_tmpdir = tempfile.mkdtemp(prefix="randeman-test-")
os.environ["RANDEMAN_DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["RANDEMAN_DOCUMENTS_DIR"] = f"{_tmpdir}/documents"
os.environ["RANDEMAN_QUARANTINE_DIR"] = f"{_tmpdir}/quarantine"
os.environ["RANDEMAN_EXPORTS_DIR"] = f"{_tmpdir}/exports"
os.environ["RANDEMAN_DOCS_ENABLED"] = "false"
os.environ["RANDEMAN_CLAMD_HOST"] = ""
os.environ["RANDEMAN_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.user import OrganizationUnit, Role, User, UserRole  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # پایگاه تست موقتی است؛ drop به دلیل چرخه FK users↔organization_units لازم نیست


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _ensure_roles(db) -> dict[str, Role]:
    codes = ["sys_admin", "senior_manager", "unit_manager", "project_manager", "employee", "pmo", "observer", "auditor"]
    roles = {}
    for code in codes:
        r = db.query(Role).filter(Role.code == code).first()
        if r is None:
            r = Role(code=code, name_fa=code)
            db.add(r)
            db.flush()
        roles[code] = r
    return roles


def _ensure_unit(db, name: str = "واحد آزمون") -> OrganizationUnit:
    unit = db.query(OrganizationUnit).filter(OrganizationUnit.name == name).first()
    if unit is None:
        unit = OrganizationUnit(name=name)
        db.add(unit)
        db.flush()
    return unit


def make_user(db, username: str, role: str, *, unit: OrganizationUnit | None = None,
              manager: User | None = None, password: str = "Test@1234") -> User:
    roles = _ensure_roles(db)
    u = db.query(User).filter(User.username == username).first()
    if u is not None:
        return u
    u = User(
        username=username, password_hash=hash_password(password),
        first_name=username, last_name="کاربر", primary_unit_id=unit.id if unit else None,
        direct_manager_id=manager.id if manager else None,
    )
    db.add(u)
    db.flush()
    db.add(UserRole(user_id=u.id, role_id=roles[role].id))
    db.flush()
    db.commit()  # برای دیده‌شدن در نشست API
    return u


@pytest.fixture()
def client(db):
    from app.main import app

    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str = "Test@1234") -> bool:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    return resp.status_code == 200


H = {"X-Requested-With": "XMLHttpRequest"}
