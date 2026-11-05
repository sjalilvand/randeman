"""شاخص‌ها — فرمول‌ها مطابق سند بخش ۷؛ مخرج صفر ⇒ «غیرقابل محاسبه» (AC-10)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import settings
from app.models.base import utcnow
from app.models.enums import TaskStatus
from app.models.task import Task
from app.models.user import User

NON_FINAL = [s for s in TaskStatus if s not in (TaskStatus.completed, TaskStatus.cancelled)]


def _pct(num: int, den: int) -> float | None:
    if den == 0:
        return None  # قابل محاسبه نیست
    return round(num / den * 100, 1)


def project_progress(db: OrmSession, project_id: uuid.UUID) -> dict:
    """پیشرفت گزارش‌شده و تأییدشده با وزن (سند ۷.۱)."""
    rows = db.execute(
        select(Task.weight, Task.progress, Task.status).where(
            Task.project_id == project_id, Task.status != TaskStatus.cancelled
        )
    ).all()
    total_w = sum(float(w or 0) for w, _, _ in rows)
    if total_w <= 0 or not rows:
        return {"reported": None, "approved": None, "reason": "فاقد داده کافی"}
    reported = sum(float(w) * float(p) for w, p, _ in rows) / total_w
    approved_w = sum(float(w) for w, _, st in rows if st == TaskStatus.completed)
    return {"reported": round(reported, 1), "approved": round(approved_w / total_w * 100, 1), "reason": None}


def overdue_pct(db: OrmSession, *, period_start: date, period_end: date, project_id: uuid.UUID | None = None,
                unit_id: uuid.UUID | None = None) -> float | None:
    """درصد تعهدات معوق در پایان دوره (سند ۷.۲) — مبنای وظایف معتبر با سررسید داخل دوره."""
    conds = [Task.current_due_date >= period_start, Task.current_due_date <= period_end,
             Task.status != TaskStatus.cancelled]
    if project_id:
        conds.append(Task.project_id == project_id)
    if unit_id:
        conds.append(Task.unit_id == unit_id)
    rows = db.execute(select(Task.status, Task.completed_at).where(*conds)).all()
    den = len(rows)
    not_approved = sum(
        1 for st, done in rows
        if not (st == TaskStatus.completed and done and done.astimezone(tz=None) and done.date() <= period_end)
    )
    return _pct(not_approved, den)


def on_time_pct(db: OrmSession, *, period_start: date, period_end: date, baseline: str = "current",
                project_id: uuid.UUID | None = None) -> float | None:
    """تکمیل به‌موقع (سند ۷.۳) — دو مبنا: base (سررسید اولیه) و current (اصلاح‌شده مصوب)."""
    due_col = Task.base_due_date if baseline == "base" else Task.current_due_date
    conds = [Task.status == TaskStatus.completed, due_col.is_not(None),
             due_col >= period_start, due_col <= period_end, Task.completed_at.is_not(None)]
    if project_id:
        conds.append(Task.project_id == project_id)
    rows = db.execute(select(due_col, Task.completed_at).where(*conds)).all()
    den = len(rows)
    on_time = sum(1 for due, done in rows if done is not None and due is not None and done.date() <= due)
    return _pct(on_time, den)


def delay_stats(db: OrmSession, *, period_start: date, period_end: date,
                project_id: uuid.UUID | None = None) -> dict:
    """تفکیک تأخیر: تا ارسال خروجی، انتظار بررسی، تا تأیید نهایی (سند ۷.۴) — روز تقویمی."""
    conds = [Task.status == TaskStatus.completed, Task.completed_at.is_not(None),
             Task.submitted_at.is_not(None),
             func.date(Task.completed_at) >= period_start, func.date(Task.completed_at) <= period_end]
    if project_id:
        conds.append(Task.project_id == project_id)
    rows = db.execute(select(Task.current_due_date, Task.submitted_at, Task.completed_at).where(*conds)).all()
    to_submit: list[float] = []
    review_wait: list[float] = []
    to_approve: list[float] = []
    for due, submitted, completed in rows:
        if due and submitted:
            to_submit.append(max(0.0, (submitted.date() - due).days))
        review_wait.append(max(0.0, (completed - submitted).total_seconds() / 86400))
        if due:
            to_approve.append(max(0.0, (completed.date() - due).days))
    def avg(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 1) if vals else None
    return {"submit_delay_avg": avg(to_submit), "review_wait_avg": avg(review_wait), "approve_delay_avg": avg(to_approve),
            "sample_size": len(rows)}


def workload_ratio(db: OrmSession, *, user: User, week_start: date) -> dict:
    """نسبت بار برنامه‌ریزی‌شده به ظرفیت (سند ۷.۵) — ساعات تخمینی وظایف فعال با سررسید در هفته."""
    week_end = week_start + timedelta(days=6)
    rows = db.execute(
        select(Task.estimated_hours, Task.id).where(
            Task.assignee_id == user.id,
            Task.status.in_(NON_FINAL),
            Task.current_due_date >= week_start,
            Task.current_due_date <= week_end,
        )
    ).all()
    capacity = float(user.capacity_hours_per_week or settings.default_weekly_capacity_hours)
    est_total = sum(float(e) for e, _ in rows if e is not None)
    with_estimate = sum(1 for e, _ in rows if e is not None)
    return {
        "ratio_pct": round(est_total / capacity * 100, 1) if capacity > 0 else None,
        "estimated_hours": est_total,
        "capacity_hours": capacity,
        "coverage_pct": _pct(with_estimate, len(rows)),
    }


def my_overdue_count(db: OrmSession, user: User) -> int:
    return int(db.scalar(
        select(func.count()).select_from(Task).where(
            Task.assignee_id == user.id, Task.status.in_(NON_FINAL),
            Task.current_due_date < utcnow().date(),
        )
    ) or 0)


def org_task_status_counts(db: OrmSession) -> dict[str, int]:
    rows = db.execute(select(Task.status, func.count()).group_by(Task.status)).all()
    return {st.value if hasattr(st, "value") else str(st): int(c) for st, c in rows}


def iso_week_label(day: date) -> str:
    start = week_start_for(day)
    return f"{start.isoformat()}..{(start + timedelta(days=6)).isoformat()}"


def week_start_for(day: date) -> date:
    from datetime import timedelta as _td

    return day - _td(days=(day.weekday() - 5) % 7)
