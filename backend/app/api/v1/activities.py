"""فعالیت‌ها: ثبت اقدامات واقعی، مستقل از وظیفه (سند ۵.۴)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.db import get_db
from app.core.permissions import can_view_activity
from app.models.activity import Activity
from app.models.enums import ActivityType
from app.models.report import ReportStatus, WeeklyReport, WeeklyReportItem
from app.models.task import Task
from app.models.user import User
from app.services.audit_svc import audit

router = APIRouter(prefix="/activities", tags=["activities"])


class ActivityIn(BaseModel):
    activity_date: date
    title: str = Field(min_length=3, max_length=250)
    description: str | None = None
    result: str | None = None
    task_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=24 * 60 * 7)
    type: ActivityType = ActivityType.execution
    blocker_note: str | None = None


def _payload(db: OrmSession, a: Activity) -> dict:
    u = db.get(User, a.user_id)
    t = db.get(Task, a.task_id) if a.task_id else None
    return {
        "id": str(a.id), "user_id": str(a.user_id), "user_name": u.full_name if u else "—",
        "activity_date": a.activity_date.isoformat(), "title": a.title, "description": a.description,
        "result": a.result,
        "task_id": str(a.task_id) if a.task_id else None,
        "task_title": t.title if t else None,
        "task_code": t.code if t else None,
        "project_id": str(a.project_id) if a.project_id else None,
        "duration_minutes": a.duration_minutes,
        "type": a.type.value, "blocker_note": a.blocker_note,
        "created_at": a.created_at.isoformat(), "version": a.version,
    }


@router.get("")
def list_activities(
    user_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None, task_id: uuid.UUID | None = None,
    date_from: date | None = None, date_to: date | None = None, type_filter: str | None = None,
    page: int = 1, size: int = 20,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    from app.core.permissions import has_role

    conds = []
    if not has_role(db, actor, "senior_manager", "pmo", "auditor", "observer"):
        if user_id and user_id != actor.id:
            # مدیر واحد: اعضای واحد خودش
            from app.core.permissions import managed_unit_ids
            from app.models.user import User as U

            uids = managed_unit_ids(db, actor)
            target = db.get(U, user_id)
            if target is None or target.primary_unit_id not in uids:
                conds.append(Activity.user_id == actor.id)
            else:
                conds.append(Activity.user_id == user_id)
        else:
            conds.append(Activity.user_id == actor.id)
    elif user_id:
        conds.append(Activity.user_id == user_id)
    if project_id:
        conds.append(Activity.project_id == project_id)
    if task_id:
        conds.append(Activity.task_id == task_id)
    if date_from:
        conds.append(Activity.activity_date >= date_from)
    if date_to:
        conds.append(Activity.activity_date <= date_to)
    if type_filter:
        try:
            conds.append(Activity.type == ActivityType(type_filter))
        except ValueError:
            raise HTTPException(422, "نوع فعالیت نامعتبر است")
    total = db.scalar(select(func.count()).select_from(Activity).where(*conds)) or 0
    rows = db.execute(
        select(Activity).where(*conds).order_by(Activity.activity_date.desc(), Activity.created_at.desc())
        .offset((page - 1) * size).limit(size)
    ).scalars().all()
    return {"items": [_payload(db, a) for a in rows], "total": int(total), "page": page, "size": size}


@router.post("", status_code=201)
def create_activity(body: ActivityIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    if body.task_id and db.get(Task, body.task_id) is None:
        raise HTTPException(404, "وظیفه یافت نشد")
    a = Activity(**body.model_dump(), user_id=actor.id)
    db.add(a)
    audit(db, actor_id=actor.id, action="activity_created", entity_type="activity", entity_id=a.id,
          summary=f"ثبت فعالیت: {a.title[:80]}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, a)


@router.put("/{activity_id}")
def update_activity(activity_id: uuid.UUID, body: ActivityIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    a = db.get(Activity, activity_id)
    if a is None or not can_view_activity(db, actor, a):
        raise HTTPException(404, "فعالیت یافت نشد")
    if a.user_id != actor.id:
        raise HTTPException(403, "فقط ثبت‌کننده می‌تواند ویرایش کند")
    # فعالیت مرتبط با گزارش تأییدشده فقط از فرایند اصلاح تغییر می‌کند (سند ۵.۴)
    linked = db.execute(
        select(WeeklyReport.id).join(WeeklyReportItem, WeeklyReportItem.report_id == WeeklyReport.id).where(
            WeeklyReportItem.activity_id == a.id, WeeklyReport.status == ReportStatus.approved
        ).limit(1)
    ).scalar()
    if linked is not None:
        raise HTTPException(422, "این فعالیت در گزارش تأییدشده آمده و قابل ویرایش مستقیم نیست")
    for field, value in body.model_dump().items():
        setattr(a, field, value)
    a.version += 1
    audit(db, actor_id=actor.id, action="activity_updated", entity_type="activity", entity_id=a.id,
          summary="ویرایش فعالیت", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, a)
