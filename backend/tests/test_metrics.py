"""آزمون شاخص‌ها: مخرج صفر ⇒ غیرقابل محاسبه (AC-10) و فرمول‌های سند ۷."""
import uuid
from datetime import date

from app.models.enums import TaskStatus
from app.models.task import Task
from app.services import metrics


def test_overdue_pct_zero_divisor(db):
    """AC-10 — مخرج صفر: قابل محاسبه نیست."""
    assert metrics.overdue_pct(db, period_start=date(2020, 1, 1), period_end=date(2020, 1, 7)) is None


def test_on_time_pct_zero_divisor(db):
    assert metrics.on_time_pct(db, period_start=date(2020, 1, 1), period_end=date(2020, 1, 7)) is None


def test_project_progress_insufficient_data(db):
    empty_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    assert metrics.project_progress(db, empty_id)["reason"] == "فاقد داده کافی"


def test_project_progress_weighted(db):
    emp = db.query(__import__("app.models.user", fromlist=["User"]).User).filter_by(username="emp-a1").first()
    from app.models.project import Project

    p = Project(code="PRJ-MX", title="پروژه شاخص")
    db.add(p)
    db.flush()
    db.add(Task(code="T-MX1", title="۱", project_id=p.id, assignee_id=emp.id, created_by=emp.id,
                status=TaskStatus.completed, progress=100, weight=3.0))
    db.add(Task(code="T-MX2", title="۲", project_id=p.id, assignee_id=emp.id, created_by=emp.id,
                status=TaskStatus.in_progress, progress=50, weight=1.0))
    db.flush()
    result = metrics.project_progress(db, p.id)
    assert result["reported"] == 87.5   # (3×100 + 1×50)/4
    assert result["approved"] == 75.0   # 3/4


def test_week_start_saturday():
    # یکشنبه ۱ نوامبر ۲۰۲۶ → شنبه ۳۱ اکتبر
    assert metrics.week_start_for(date(2026, 11, 1)).isoformat() == "2026-10-31"
    assert metrics.week_start_for(date(2026, 10, 24)).isoformat() == "2026-10-24"  # خود شنبه
    assert metrics.week_start_for(date(2026, 10, 28)).isoformat() == "2026-10-24"  # چهارشنبه
