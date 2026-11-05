"""گزارش‌گیری: خروجی Excel (سند ۶ و ۱۲.۴) — حجم بالا در Worker (پاسخ 202)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.db import get_db
from app.core.permissions import has_role, task_visibility_filter
from app.models.base import utcnow
from app.models.enums import TaskStatus
from app.models.ops import BackgroundJob
from app.models.task import Task
from app.models.user import User
from app.services import excel
from app.services.audit_svc import audit

router = APIRouter(prefix="/reports", tags=["reports"])

INLINE_ROW_LIMIT = 5000


def _task_rows(db: OrmSession, actor: User, **filters):  # noqa: ANN003
    conds = []
    flt = task_visibility_filter(db, actor)
    if flt is not None:
        conds.extend(flt)
    if filters.get("status_filter"):
        conds.append(Task.status == TaskStatus(filters["status_filter"]))
    if filters.get("project_id"):
        conds.append(Task.project_id == filters["project_id"])
    if filters.get("assignee_id"):
        conds.append(Task.assignee_id == filters["assignee_id"])
    if filters.get("overdue_only"):
        conds.append(Task.current_due_date < utcnow().date())
    total = int(db.scalar(select(func.count()).select_from(Task).where(*conds)) or 0)
    rows = db.execute(select(Task).where(*conds).order_by(Task.created_at.desc()).limit(total)).scalars().all()
    return rows


@router.get("/tasks.xlsx")
def export_tasks(
    request: Request,
    status_filter: str | None = None, project_id=None, assignee_id=None, overdue_only: bool = False,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
):
    rows = _task_rows(db, actor, status_filter=status_filter, project_id=project_id,
                      assignee_id=assignee_id, overdue_only=overdue_only)
    if len(rows) > INLINE_ROW_LIMIT:
        job = BackgroundJob(type="export_tasks_excel", payload={
            "filters": {"status": status_filter, "overdue": overdue_only},
            "requested_by": str(actor.id),
        })
        db.add(job)
        db.flush()
        return {"queued": True, "job_id": str(job.id)}  # 202 از طریق router پاسخ پیش‌فرض 200؛ مستند می‌شود
    cols = ["کد", "عنوان", "مسئول", "وضعیت", "اولویت", "پیشرفت", "سررسید جاری", "سررسید مبنا", "وزن", "پروژه"]
    data = []
    for t in rows:
        assignee = db.get(User, t.assignee_id)
        data.append([
            t.code, t.title, assignee.full_name if assignee else "—", t.status.value, t.priority.value,
            f"{t.progress}%", excel.jdate_str(t.current_due_date), excel.jdate_str(t.base_due_date),
            t.weight, str(t.project_id) if t.project_id else "—",
        ])
    buf = excel.build_workbook(title="گزارش وظایف", period_label=None,
                               filters_label=request.url.query or None, columns=cols, rows=data,
                               generated_by=actor.full_name)
    audit(db, actor_id=actor.id, action="report_exported", entity_type="report", summary="خروجی Excel وظایف",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    filename = "tasks-report.xlsx"
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/activities.xlsx")
def export_activities(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    from app.models.activity import Activity

    conds = []
    if not has_role(db, actor, "senior_manager", "pmo", "auditor", "observer"):
        conds.append(Activity.user_id == actor.id)
    rows = db.execute(select(Activity).where(*conds).order_by(Activity.activity_date.desc()).limit(INLINE_ROW_LIMIT)).scalars().all()
    cols = ["کاربر", "تاریخ", "عنوان", "نوع", "مدت (دقیقه)", "وظیفه", "مانع"]
    data = []
    for a in rows:
        u = db.get(User, a.user_id)
        t = db.get(Task, a.task_id) if a.task_id else None
        data.append([u.full_name if u else "—", excel.jdate_str(a.activity_date), a.title, a.type.value,
                     a.duration_minutes, t.code if t else "—", a.blocker_note or "—"])
    buf = excel.build_workbook(title="گزارش فعالیت‌ها", period_label=None, filters_label=None,
                               columns=cols, rows=data, generated_by=actor.full_name)
    filename = "activities-report.xlsx"
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/metrics")
def metrics_report(
    project_id=None, period_start=None, period_end=None,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
):
    from datetime import date as _date

    from app.services import metrics as m

    if not has_role(db, actor, "senior_manager", "pmo", "auditor"):
        raise PermissionError("مجوز مشاهده شاخص‌های تحلیلی را ندارید")
    today = utcnow().date()
    ps = _date.fromisoformat(period_start) if period_start else today.replace(month=1, day=1)
    pe = _date.fromisoformat(period_end) if period_end else today
    pid = project_id
    return {
        "period": {"start": ps.isoformat(), "end": pe.isoformat()},
        "overdue_pct": m.overdue_pct(db, period_start=ps, period_end=pe, project_id=pid),
        "on_time_current": m.on_time_pct(db, period_start=ps, period_end=pe, baseline="current", project_id=pid),
        "on_time_base": m.on_time_pct(db, period_start=ps, period_end=pe, baseline="base", project_id=pid),
        "delays": m.delay_stats(db, period_start=ps, period_end=pe, project_id=pid),
        "project_progress": m.project_progress(db, pid) if pid else None,
    }
