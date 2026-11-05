"""وظایف: CRUD، گردش وضعیت، وابستگی، درخواست تغییر سررسید و تاریخچه (سند ۵.۳ و ۱۱.۲)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.db import get_db
from app.core.permissions import can_manage_task, can_review_task, can_view_task, has_role, task_visibility_filter
from app.models.base import utcnow
from app.models.document import Document, DocumentLink
from app.models.enums import ChangeRequestStatus, Complexity, Priority, TaskStatus
from app.models.ops import Blocker
from app.models.project import Project
from app.models.task import (
    Task, TaskChangeLog, TaskChangeRequest, TaskCollaborator, TaskDependency, TaskStatusHistory,
)
from app.models.user import OrganizationUnit, User
from app.services import notify, task_service
from app.services.audit_svc import audit

router = APIRouter(prefix="/tasks", tags=["tasks"])


def new_task_code(db: OrmSession) -> str:
    import secrets

    while True:
        code = "T-" + "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))
        if db.scalar(select(Task.id).where(Task.code == code)) is None:
            return code


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    description: str | None = None
    project_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    assignee_id: uuid.UUID
    approver_id: uuid.UUID | None = None
    planned_start: date | None = None
    base_due_date: date | None = None
    current_due_date: date | None = None
    estimated_hours: float | None = Field(default=None, ge=0, le=10000)
    priority: Priority = Priority.medium
    complexity: Complexity = Complexity.medium
    weight: float = Field(default=1.0, gt=0, le=100)
    acceptance_criteria: str | None = None
    required_documents: str | None = None


class ActionIn(BaseModel):
    reason: str | None = None
    comment: str | None = None
    delivery_note: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    new_due_date: date | None = None
    approve: bool | None = None


def _payload(db: OrmSession, t: Task, brief: bool = False) -> dict:
    assignee = db.get(User, t.assignee_id)
    creator = db.get(User, t.created_by)
    approver = db.get(User, t.approver_id) if t.approver_id else None
    project = db.get(Project, t.project_id) if t.project_id else None
    unit = db.get(OrganizationUnit, t.unit_id) if t.unit_id else None
    data = {
        "id": str(t.id), "code": t.code, "title": t.title, "description": t.description,
        "project_id": str(t.project_id) if t.project_id else None,
        "project_title": project.title if project else None,
        "unit_id": str(t.unit_id) if t.unit_id else None,
        "unit_name": unit.name if unit else None,
        "assignee_id": str(t.assignee_id), "assignee_name": assignee.full_name if assignee else "—",
        "approver_id": str(t.approver_id) if t.approver_id else None,
        "approver_name": approver.full_name if approver else None,
        "created_by": str(t.created_by), "created_by_name": creator.full_name if creator else "—",
        "planned_start": t.planned_start.isoformat() if t.planned_start else None,
        "base_due_date": t.base_due_date.isoformat() if t.base_due_date else None,
        "current_due_date": t.current_due_date.isoformat() if t.current_due_date else None,
        "estimated_hours": t.estimated_hours,
        "priority": t.priority.value, "complexity": t.complexity.value, "weight": t.weight,
        "progress": t.progress, "status": t.status.value,
        "acceptance_criteria": t.acceptance_criteria, "blocked_reason": t.blocked_reason,
        "delivery_note": t.delivery_note,
        "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat(), "version": t.version,
    }
    if brief:
        return data
    collab_rows = db.execute(select(TaskCollaborator).where(TaskCollaborator.task_id == t.id)).scalars().all()
    collabs = []
    for c in collab_rows:
        cu = db.get(User, c.user_id)
        collabs.append({"user_id": str(c.user_id), "full_name": cu.full_name if cu else "—"})
    deps = db.execute(select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == t.id)).scalars().all()
    dep_list = []
    for dep_id in deps:
        d = db.get(Task, dep_id)
        dep_list.append({"task_id": str(dep_id), "code": d.code if d else "—", "title": d.title if d else "—",
                         "status": d.status.value if d else None})
    history = db.execute(
        select(TaskStatusHistory).where(TaskStatusHistory.task_id == t.id).order_by(TaskStatusHistory.created_at.desc())
    ).scalars().all()
    change_reqs = db.execute(
        select(TaskChangeRequest).where(TaskChangeRequest.task_id == t.id).order_by(TaskChangeRequest.created_at.desc())
    ).scalars().all()
    docs = db.execute(
        select(Document).join(DocumentLink, DocumentLink.document_id == Document.id).where(
            DocumentLink.entity_type == "task", DocumentLink.entity_id == t.id
        ).order_by(Document.created_at.desc())
    ).scalars().all()
    return {**data, "collaborators": collabs, "dependencies": dep_list,
            "history": [{"from": h.from_status, "to": h.to_status, "at": h.created_at.isoformat(),
                         "reason": h.reason, "actor": (db.get(User, h.actor_id).full_name if h.actor_id and db.get(User, h.actor_id) else "—")}
                        for h in history],
            "change_requests": [{"id": str(c.id), "field": c.field, "old_value": c.old_value, "new_value": c.new_value,
                                 "reason": c.reason, "status": c.status.value,
                                 "requested_by": (db.get(User, c.requested_by).full_name if db.get(User, c.requested_by) else "—"),
                                 "decision_note": c.decision_note} for c in change_reqs],
            "documents": [{"id": str(d.id), "title": d.title, "status": d.status.value, "version": int(d.version)} for d in docs]}


def _get_task_or_404(db: OrmSession, task_id: uuid.UUID, actor: User) -> Task:
    t = db.get(Task, task_id)
    if t is None or not can_view_task(db, actor, t):
        raise HTTPException(404, "وظیفه یافت نشد")
    return t


def _load_assignable(db: OrmSession, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None or not u.is_active:
        raise HTTPException(404, "مسئول اصلی معتبر نیست")
    return u


@router.get("")
def list_tasks(
    status_filter: str | None = None, project_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None, unit_id: uuid.UUID | None = None,
    overdue_only: bool = False, q: str | None = None,
    due_from: date | None = None, due_to: date | None = None,
    sort: str = "created_desc", page: int = 1, size: int = 20,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    conds = []
    flt = task_visibility_filter(db, actor)
    if flt is not None:
        conds.extend(flt)
    if status_filter:
        try:
            conds.append(Task.status == TaskStatus(status_filter))
        except ValueError:
            raise HTTPException(422, "وضعیت نامعتبر است")
    if project_id:
        conds.append(Task.project_id == project_id)
    if assignee_id:
        conds.append(Task.assignee_id == assignee_id)
    if unit_id:
        conds.append(Task.unit_id == unit_id)
    if overdue_only:
        conds.append(Task.current_due_date < utcnow().date())
        conds.append(Task.status.in_([s for s in TaskStatus if s not in (TaskStatus.completed, TaskStatus.cancelled)]))
    if due_from:
        conds.append(Task.current_due_date >= due_from)
    if due_to:
        conds.append(Task.current_due_date <= due_to)
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Task.title.ilike(like), Task.code.ilike(like), Task.description.ilike(like)))
    order = {"created_desc": Task.created_at.desc(), "due_asc": Task.current_due_date.asc().nullslast(),
             "priority_desc": Task.priority.desc()}.get(sort, Task.created_at.desc())
    total = db.scalar(select(func.count()).select_from(Task).where(*conds)) or 0
    rows = db.execute(select(Task).where(*conds).order_by(order).offset((page - 1) * size).limit(size)).scalars().all()
    return {"items": [_payload(db, t, brief=True) for t in rows], "total": int(total), "page": page, "size": size}


@router.post("", status_code=201)
def create_task(body: TaskIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    assignee = _load_assignable(db, body.assignee_id)
    t = Task(**body.model_dump(), code=new_task_code(db), created_by=actor.id, status=TaskStatus.assigned)
    if body.project_id and db.get(Project, body.project_id) is None:
        raise HTTPException(404, "پروژه یافت نشد")
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز تخصیص کار ندارید (سند ۴.۳)")
    if body.base_due_date and body.current_due_date is None:
        t.current_due_date = body.base_due_date
    db.add(t)
    db.flush()
    db.add(TaskStatusHistory(task_id=t.id, from_status=None, to_status=TaskStatus.assigned.value, actor_id=actor.id,
                             reason="ایجاد و تخصیص"))
    notify.notify(db, user_id=assignee.id, type="task.assigned", title=f"وظیفه جدید: {t.title}",
                  entity_type="task", entity_id=t.id)
    audit(db, actor_id=actor.id, action="task_created", entity_type="task", entity_id=t.id,
          summary=f"ایجاد وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.get("/{task_id}")
def get_task(task_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    return _payload(db, t)


@router.put("/{task_id}")
def update_task(task_id: uuid.UUID, body: TaskIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ویرایش وظیفه ندارید")
    tracked = {"current_due_date": t.current_due_date, "assignee_id": t.assignee_id, "weight": t.weight,
               "acceptance_criteria": t.acceptance_criteria, "approver_id": t.approver_id}
    for field, value in body.model_dump().items():
        setattr(t, field, value)
    if body.base_due_date and body.current_due_date is None:
        t.current_due_date = body.base_due_date
    for field, old in tracked.items():
        new = getattr(t, field)
        if old != new:
            task_service.log_change(db, task=t, field=field, old=old, new=new, actor=actor)
            if field == "assignee_id" and new:
                notify.notify(db, user_id=new, type="task.assigned", title=f"وظیفه {t.code} به شما تخصیص یافت",
                              entity_type="task", entity_id=t.id)
    t.version += 1
    audit(db, actor_id=actor.id, action="task_updated", entity_type="task", entity_id=t.id,
          summary=f"ویرایش وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/start")
def start_task(task_id: uuid.UUID, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if actor.id != t.assignee_id and not can_manage_task(db, actor, t):
        raise HTTPException(403, "فقط مسئول یا مقام مجاز می‌تواند شروع کند")
    task_service.transition(db, task=t, to_status=TaskStatus.in_progress, actor=actor, reason="شروع انجام")
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/submit-for-review")
def submit_for_review(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    task_service.submit_for_review(db, task=t, actor=actor, delivery_note=body.delivery_note or body.reason or "")
    if t.approver_id:
        notify.notify(db, user_id=t.approver_id, type="task.review_requested",
                      title=f"بررسی خروجی وظیفه {t.code}", entity_type="task", entity_id=t.id)
    audit(db, actor_id=actor.id, action="task_submitted", entity_type="task", entity_id=t.id,
          summary=f"ارسال خروجی وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/approve")
def approve(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_review_task(db, actor, t):
        raise HTTPException(403, "فقط شخص مجاز می‌تواند تأیید کند")
    if t.assignee_id == actor.id and t.approver_id != actor.id:
        raise HTTPException(403, "تأیید کار خود توسط همان فرد ممنوع است")
    task_service.approve(db, task=t, actor=actor, comment=body.comment)
    notify.notify(db, user_id=t.assignee_id, type="task.approved", title=f"وظیفه {t.code} تأیید شد",
                  entity_type="task", entity_id=t.id)
    audit(db, actor_id=actor.id, action="task_approved", entity_type="task", entity_id=t.id,
          summary=f"تأیید وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/request-correction")
def request_correction(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_review_task(db, actor, t):
        raise HTTPException(403, "فقط شخص مجاز می‌تواند اصلاح بخواهد")
    if not (body.reason or "").strip():
        raise HTTPException(422, "ثبت دلیل برای درخواست اصلاح الزامی است")
    task_service.request_correction(db, task=t, actor=actor, reason=body.reason)
    notify.notify(db, user_id=t.assignee_id, type="task.correction_requested",
                  title=f"اصلاح خروجی وظیفه {t.code} لازم است", body=body.reason, entity_type="task", entity_id=t.id)
    audit(db, actor_id=actor.id, action="task_correction_requested", entity_type="task", entity_id=t.id,
          summary=f"درخواست اصلاح وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/block")
def block(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if actor.id != t.assignee_id and not can_manage_task(db, actor, t):
        raise HTTPException(403, "فقط مسئول اصلی یا مقام مجاز می‌تواند متوقف کند")
    if not (body.reason or "").strip():
        raise HTTPException(422, "ثبت مانع الزامی است")
    task_service.block(db, task=t, actor=actor, reason=body.reason.strip())
    managers = set()
    if t.unit_id:
        unit = db.get(OrganizationUnit, t.unit_id)
        if unit and unit.manager_id:
            managers.add(unit.manager_id)
    for uid in managers:
        notify.notify(db, user_id=uid, type="task.blocked", title=f"توقف وظیفه {t.code}", body=body.reason,
                      entity_type="task", entity_id=t.id)
    audit(db, actor_id=actor.id, action="task_blocked", entity_type="task", entity_id=t.id,
          summary=f"توقف وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/unblock")
def unblock(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if actor.id != t.assignee_id and not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ندارید")
    task_service.unblock(db, task=t, actor=actor, note=body.reason)
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/cancel")
def cancel(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز لغو ندارید")
    if not (body.reason or "").strip():
        raise HTTPException(422, "ثبت دلیل و اختیار معتبر برای لغو الزامی است")
    task_service.transition(db, task=t, to_status=TaskStatus.cancelled, actor=actor, reason=body.reason)
    audit(db, actor_id=actor.id, action="task_cancelled", entity_type="task", entity_id=t.id,
          summary=f"لغو وظیفه {t.code}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/reopen")
def reopen(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not has_role(db, actor, "senior_manager", "pmo", "unit_manager", "project_manager"):
        raise HTTPException(403, "بازگشایی نیازمند مجوز مدیریتی است")
    task_service.reopen(db, task=t, actor=actor, reason=body.reason or "")
    audit(db, actor_id=actor.id, action="task_reopened", entity_type="task", entity_id=t.id,
          summary=f"بازگشایی وظیفه {t.code}", detail={"reason": body.reason},
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/progress")
def set_progress(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if actor.id != t.assignee_id and not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ندارید")
    if body.progress is None:
        raise HTTPException(422, "درصد پیشرفت الزامی است")
    if t.status == TaskStatus.completed:
        raise HTTPException(422, "پیشرفت وظیفه تکمیل‌شده تغییر نمی‌کند")
    old = t.progress
    t.progress = body.progress
    if t.status == TaskStatus.assigned and body.progress > 0:
        task_service.transition(db, task=t, to_status=TaskStatus.in_progress, actor=actor, reason="ثبت پیشرفت")
    task_service.log_change(db, task=t, field="progress", old=old, new=body.progress, actor=actor)
    db.flush()
    return _payload(db, t)


@router.post("/{task_id}/request-due-date-change", status_code=201)
def request_due_change(task_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if actor.id != t.assignee_id and not can_manage_task(db, actor, t):
        raise HTTPException(403, "فقط مسئول اصلی می‌تواند تغییر مهلت بخواهد")
    if not body.new_due_date:
        raise HTTPException(422, "سررسید جدید الزامی است")
    if not (body.reason or "").strip():
        raise HTTPException(422, "ثبت دلیل تغییر مهلت الزامی است")
    cr = TaskChangeRequest(
        task_id=t.id, requested_by=actor.id, field="current_due_date",
        old_value=t.current_due_date.isoformat() if t.current_due_date else None,
        new_value=body.new_due_date.isoformat(), reason=body.reason,
    )
    db.add(cr)
    db.flush()
    decider = t.approver_id
    if not decider and t.unit_id:
        unit = db.get(OrganizationUnit, t.unit_id)
        decider = unit.manager_id if unit else None
    if decider:
        notify.notify(db, user_id=decider, type="task.due_change_requested",
                      title=f"درخواست تغییر سررسید وظیفه {t.code}", entity_type="task", entity_id=t.id)
    return {"id": str(cr.id), "status": cr.status.value}


@router.post("/{task_id}/due-change-requests/{request_id}/decide")
def decide_due_change(task_id: uuid.UUID, request_id: uuid.UUID, body: ActionIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_review_task(db, actor, t):
        raise HTTPException(403, "مجوز تصمیم‌گیری ندارید")
    cr = db.get(TaskChangeRequest, request_id)
    if cr is None or cr.task_id != t.id:
        raise HTTPException(404, "درخواست یافت نشد")
    if cr.status != ChangeRequestStatus.pending:
        raise HTTPException(422, "این درخواست تصمیم‌گیری شده است")
    if body.approve is None:
        raise HTTPException(422, "تصمیم (approve) الزامی است")
    cr.status = ChangeRequestStatus.approved if body.approve else ChangeRequestStatus.rejected
    cr.decided_by = actor.id
    cr.decided_at = utcnow()
    cr.decision_note = body.comment
    if cr.status == ChangeRequestStatus.approved:
        old = t.current_due_date
        t.current_due_date = date.fromisoformat(cr.new_value)
        task_service.log_change(db, task=t, field="current_due_date", old=old, new=t.current_due_date,
                                actor=actor, reason=cr.reason)
    audit(db, actor_id=actor.id, action="task_due_change_decided", entity_type="task", entity_id=t.id,
          summary=f"تصمیم تغییر سررسید {t.code}: {cr.status.value}",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return {"status": cr.status.value}


@router.post("/{task_id}/collaborators", status_code=201)
def add_collaborator(task_id: uuid.UUID, body: dict, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ندارید")
    uid = body.get("user_id")
    u = db.get(User, uuid.UUID(uid)) if uid else None
    if u is None or not u.is_active:
        raise HTTPException(404, "کاربر یافت نشد")
    if u.id == t.assignee_id:
        raise HTTPException(422, "مسئول اصلی به‌عنوان همکار اضافه نمی‌شود")
    if db.scalar(select(TaskCollaborator).where(TaskCollaborator.task_id == t.id, TaskCollaborator.user_id == u.id)) is None:
        db.add(TaskCollaborator(task_id=t.id, user_id=u.id, note=body.get("note")))
    return {"ok": True}


@router.delete("/{task_id}/collaborators/{user_id}")
def remove_collaborator(task_id: uuid.UUID, user_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ندارید")
    db.execute(delete(TaskCollaborator).where(TaskCollaborator.task_id == t.id, TaskCollaborator.user_id == user_id))
    return {"ok": True}


@router.post("/{task_id}/dependencies", status_code=201)
def add_dependency(task_id: uuid.UUID, body: dict, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ندارید")
    dep_id = body.get("depends_on_task_id")
    if not dep_id:
        raise HTTPException(422, "شناسه وظیفه وابسته الزامی است")
    task_service.add_dependency(db, task=t, depends_on_task_id=uuid.UUID(dep_id))
    return {"ok": True}


@router.delete("/{task_id}/dependencies/{dep_id}")
def remove_dependency(task_id: uuid.UUID, dep_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    t = _get_task_or_404(db, task_id, actor)
    if not can_manage_task(db, actor, t):
        raise HTTPException(403, "مجوز ندارید")
    db.execute(delete(TaskDependency).where(TaskDependency.task_id == t.id, TaskDependency.depends_on_task_id == dep_id))
    return {"ok": True}


@router.get("/{task_id}/history")
def history(task_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> list[dict]:
    t = _get_task_or_404(db, task_id, actor)
    rows = db.execute(select(TaskChangeLog).where(TaskChangeLog.task_id == t.id).order_by(TaskChangeLog.created_at.desc())).scalars().all()
    return [{"field": r.field, "old": r.old_value, "new": r.new_value, "reason": r.reason,
             "at": r.created_at.isoformat(), "actor": (db.get(User, r.actor_id).full_name if r.actor_id and db.get(User, r.actor_id) else "—")}
            for r in rows]
