"""داشبوردها — فردی، واحدی، پروژه‌ای و سازمانی (سند ۶).

هر عدد به اقلام تشکیل‌دهنده متصل است؛ فیلترهای داشبورد با فهرست جزئیات یکسان است.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_current_user
from app.core.db import get_db
from app.core.permissions import has_role, managed_unit_ids
from app.models.base import utcnow
from app.models.enums import BlockerStatus, ProjectStatus, ReportStatus, TaskStatus
from app.models.ops import Blocker, Notification
from app.models.project import Project
from app.models.report import WeeklyReport
from app.models.task import Task
from app.models.user import User
from app.services import metrics, report_service
from app.services.metrics import org_task_status_counts

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

NON_FINAL = [s for s in TaskStatus if s not in (TaskStatus.completed, TaskStatus.cancelled)]


@router.get("/me")
def my_dashboard(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    today = utcnow().date()
    soon = today + timedelta(days=7)
    my_open = db.execute(
        select(Task).where(Task.assignee_id == actor.id, Task.status.in_(NON_FINAL))
        .order_by(Task.current_due_date.asc().nullslast()).limit(10)
    ).scalars().all()

    def brief(t: Task) -> dict:
        return {"id": str(t.id), "code": t.code, "title": t.title, "status": t.status.value,
                "priority": t.priority.value, "progress": t.progress,
                "current_due_date": t.current_due_date.isoformat() if t.current_due_date else None}

    ws = report_service.week_start_for(today)
    week_report = db.scalar(select(WeeklyReport).where(WeeklyReport.user_id == actor.id, WeeklyReport.week_start == ws))
    pending_corrections = int(db.scalar(select(func.count()).select_from(Task).where(
        Task.assignee_id == actor.id, Task.status == TaskStatus.needs_correction)) or 0)
    review_waiting = int(db.scalar(select(func.count()).select_from(Task).where(
        Task.approver_id == actor.id, Task.status == TaskStatus.ready_for_review)) or 0)
    unread = int(db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == actor.id, Notification.is_read.is_(False))) or 0)
    overdue = metrics.my_overdue_count(db, actor)
    return {
        "computed_at": utcnow().isoformat(),
        "cards": {"open_tasks": len(my_open), "overdue": overdue, "pending_corrections": pending_corrections,
                  "review_waiting": review_waiting, "unread_notifications": unread},
        "my_tasks": [brief(t) for t in my_open],
        "week_report": {"week_start": ws.isoformat(), "status": week_report.status.value if week_report else "none"},
        "workload": metrics.workload_ratio(db, user=actor, week_start=ws),
    }


@router.get("/org")
def org_dashboard(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    if not has_role(db, actor, "senior_manager", "pmo"):
        raise HTTPException(403, "داشبورد سازمانی نیازمند مجوز است (سند ۴.۳)")
    today = utcnow().date()
    projects_by_status = dict(db.execute(select(Project.status, func.count()).group_by(Project.status)).all())
    open_blockers = int(db.scalar(select(func.count()).select_from(Blocker).where(
        Blocker.status == BlockerStatus.open)) or 0)
    decisions_waiting = int(db.scalar(select(func.count()).select_from(Blocker).where(
        Blocker.status == BlockerStatus.open, Blocker.decision_needed.is_not(None))) or 0)
    overdue_rows = db.execute(
        select(Task).where(Task.status.in_(NON_FINAL), Task.current_due_date < today)
        .order_by(Task.current_due_date.asc()).limit(10)
    ).scalars().all()
    overdue_list = [{"code": t.code, "title": t.title, "due": t.current_due_date.isoformat() if t.current_due_date else None,
                     "assignee": (db.get(User, t.assignee_id).full_name if db.get(User, t.assignee_id) else "—"),
                     "project_id": str(t.project_id) if t.project_id else None} for t in overdue_rows]
    # نرخ ارسال گزارش ۴ هفته اخیر
    ws = report_service.week_start_for(today)
    submission = []
    for i in range(4):
        start = ws - timedelta(days=7 * i)
        total = int(db.scalar(select(func.count()).select_from(WeeklyReport).where(WeeklyReport.week_start == start)) or 0)
        submitted = int(db.scalar(select(func.count()).select_from(WeeklyReport).where(
            WeeklyReport.week_start == start, WeeklyReport.status.in_([ReportStatus.submitted, ReportStatus.in_review, ReportStatus.approved]))) or 0)
        submission.append({"week_start": start.isoformat(), "total": total, "submitted": submitted})
    return {
        "computed_at": utcnow().isoformat(),
        "projects_by_status": {k.value if hasattr(k, "value") else str(k): int(v) for k, v in projects_by_status.items()},
        "tasks_by_status": org_task_status_counts(db),
        "open_blockers": open_blockers, "decisions_waiting": decisions_waiting,
        "overdue_top": overdue_list, "weekly_submission": submission,
    }


@router.get("/unit")
def unit_dashboard(unit_id: uuid.UUID | None = None, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    uids = managed_unit_ids(db, actor)
    if not has_role(db, actor, "senior_manager", "pmo") and not uids:
        raise HTTPException(403, "شما مدیر واحد نیستید")
    target = unit_id if unit_id else (sorted(uids)[0] if uids else None)
    if target is None:
        raise HTTPException(422, "واحدی برای نمایش وجود ندارد")
    if target not in uids and not has_role(db, actor, "senior_manager", "pmo"):
        raise HTTPException(403, "این واحد در محدوده شما نیست")
    members = db.execute(select(User).where(User.primary_unit_id == target, User.is_active.is_(True))).scalars().all()
    ws = report_service.week_start_for(utcnow().date())
    member_rows = []
    for m in members:
        open_count = int(db.scalar(select(func.count()).select_from(Task).where(
            Task.assignee_id == m.id, Task.status.in_(NON_FINAL))) or 0)
        late = metrics.my_overdue_count(db, m)
        load = metrics.workload_ratio(db, user=m, week_start=ws)
        member_rows.append({"user_id": str(m.id), "full_name": m.full_name, "open_tasks": open_count,
                            "overdue": late, "workload_pct": load["ratio_pct"], "coverage_pct": load["coverage_pct"]})
    waiting_review = db.execute(
        select(Task).where(Task.unit_id == target, Task.status == TaskStatus.ready_for_review).limit(10)
    ).scalars().all()
    return {"computed_at": utcnow().isoformat(), "unit_id": str(target),
            "members": member_rows,
            "waiting_review": [{"code": t.code, "title": t.title, "assignee": (db.get(User, t.assignee_id).full_name if db.get(User, t.assignee_id) else "—"),
                                "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None} for t in waiting_review]}


@router.get("/project/{project_id}")
def project_dashboard(project_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    from app.core.permissions import can_view_project

    p = db.get(Project, project_id)
    if p is None or not can_view_project(db, actor, p):
        raise HTTPException(404, "پروژه یافت نشد")
    status_counts = dict(db.execute(select(Task.status, func.count()).where(Task.project_id == p.id).group_by(Task.status)).all())
    today = utcnow().date()
    critical = db.execute(
        select(Task).where(Task.project_id == p.id, Task.status.in_(NON_FINAL),
                           Task.current_due_date < today + timedelta(days=7))
        .order_by(Task.current_due_date.asc()).limit(10)
    ).scalars().all()
    open_blockers = db.execute(select(Blocker).where(Blocker.project_id == p.id, Blocker.status == BlockerStatus.open)).scalars().all()
    return {
        "computed_at": utcnow().isoformat(),
        "progress": metrics.project_progress(db, p.id),
        "tasks_by_status": {k.value if hasattr(k, "value") else str(k): int(v) for k, v in status_counts.items()},
        "critical_tasks": [{"code": t.code, "title": t.title, "due": t.current_due_date.isoformat() if t.current_due_date else None,
                            "progress": t.progress, "status": t.status.value} for t in critical],
        "open_blockers": [{"id": str(b.id), "title": b.title, "type": b.type.value,
                           "decision_needed": b.decision_needed} for b in open_blockers],
    }
