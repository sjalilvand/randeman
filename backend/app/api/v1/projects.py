"""پروژه‌ها: فهرست، جزئیات، اعضا، نقاط عطف و پیشرفت (سند ۵.۲)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user, require_roles
from app.core.db import get_db
from app.core.permissions import can_view_project, has_role, project_visibility_filter
from app.models.base import utcnow
from app.models.enums import ProjectStatus
from app.models.ops import Blocker, BlockerStatus
from app.models.project import Milestone, Project, ProjectMember, ProjectUnit
from app.models.task import Task
from app.models.user import OrganizationUnit, User
from app.services import metrics
from app.services.audit_svc import audit

router = APIRouter(prefix="/projects", tags=["projects"])

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _new_code(db: OrmSession) -> str:
    import secrets

    while True:
        code = "PRJ-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if db.scalar(select(Project.id).where(Project.code == code)) is None:
            return code


class ProjectIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    goal: str | None = None
    category: str | None = Field(default=None, max_length=80)
    sponsor: str | None = Field(default=None, max_length=120)
    manager_id: uuid.UUID | None = None
    lead_unit_id: uuid.UUID | None = None
    status: ProjectStatus = ProjectStatus.draft
    priority: str = "medium"
    confidentiality: str = "internal"
    start_date: date | None = None
    end_date: date | None = None
    expected_outputs: str | None = None
    acceptance_criteria: str | None = None


def _payload(db: OrmSession, p: Project) -> dict:
    from app.models.enums import Confidentiality, Priority

    mgr = db.get(User, p.manager_id) if p.manager_id else None
    unit = db.get(OrganizationUnit, p.lead_unit_id) if p.lead_unit_id else None
    task_count = int(db.scalar(select(func.count()).select_from(Task).where(
        Task.project_id == p.id, Task.status != TaskStatus.cancelled)) or 0)
    prog = metrics.project_progress(db, p.id)
    return {
        "id": str(p.id), "code": p.code, "title": p.title, "description": p.description, "goal": p.goal,
        "category": p.category, "sponsor": p.sponsor,
        "manager_id": str(p.manager_id) if p.manager_id else None,
        "manager_name": mgr.full_name if mgr else None,
        "lead_unit_id": str(p.lead_unit_id) if p.lead_unit_id else None,
        "lead_unit_name": unit.name if unit else None,
        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
        "priority": p.priority.value if hasattr(p.priority, "value") else str(p.priority),
        "confidentiality": p.confidentiality.value if hasattr(p.confidentiality, "value") else str(p.confidentiality),
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "expected_outputs": p.expected_outputs, "acceptance_criteria": p.acceptance_criteria,
        "task_count": task_count, "progress_reported": prog["reported"], "progress_approved": prog["approved"],
        "version": p.version,
    }


def _manageable(actor: User, db: OrmSession) -> bool:
    return has_role(db, actor, "senior_manager", "pmo", "unit_manager", "project_manager")


@router.get("")
def list_projects(
    status_filter: str | None = None, q: str | None = None, page: int = 1, size: int = 20,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    flt = project_visibility_filter(db, actor)
    conds = list(flt) if flt is not None else []
    if status_filter:
        conds.append(Project.status == status_filter)
    if q:
        conds.append(Project.title.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(Project).where(*conds)) or 0
    rows = db.execute(
        select(Project).where(*conds).order_by(Project.created_at.desc()).offset((page - 1) * size).limit(size)
    ).scalars().all()
    return {"items": [_payload(db, p) for p in rows], "total": int(total), "page": page, "size": size}


@router.post("", status_code=201)
def create_project(
    body: ProjectIn, request: Request,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    if not _manageable(actor, db):
        raise HTTPException(403, "مجوز ایجاد پروژه ندارید")
    p = Project(**body.model_dump(), code=_new_code(db), created_by=actor.id)
    if body.manager_id and db.get(User, body.manager_id) is None:
        raise HTTPException(404, "مدیر پروژه یافت نشد")
    if body.lead_unit_id and db.get(OrganizationUnit, body.lead_unit_id) is None:
        raise HTTPException(404, "واحد راهبر یافت نشد")
    db.add(p)
    db.flush()
    if p.manager_id:
        db.add(ProjectMember(project_id=p.id, user_id=p.manager_id, role_in_project="manager"))
    else:
        db.add(ProjectMember(project_id=p.id, user_id=actor.id, role_in_project="manager"))
        p.manager_id = actor.id
    if p.status == ProjectStatus.draft and has_role(db, actor, "senior_manager", "pmo") is False:
        p.status = ProjectStatus.draft
    audit(db, actor_id=actor.id, action="project_created", entity_type="project", entity_id=p.id,
          summary=f"ایجاد پروژه {p.title}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, p)


@router.get("/{project_id}")
def get_project(project_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    p = db.get(Project, project_id)
    if p is None or not can_view_project(db, actor, p):
        raise HTTPException(404, "پروژه یافت نشد")
    members = db.execute(
        select(ProjectMember).where(ProjectMember.project_id == p.id)
    ).scalars().all()
    member_list = []
    for m in members:
        u = db.get(User, m.user_id)
        member_list.append({"user_id": str(m.user_id), "full_name": u.full_name if u else "—",
                            "role_in_project": m.role_in_project})
    milestones = db.execute(
        select(Milestone).where(Milestone.project_id == p.id).order_by(Milestone.due_date)
    ).scalars().all()
    units = db.execute(select(ProjectUnit).where(ProjectUnit.project_id == p.id)).scalars().all()
    unit_names = []
    for pu in units:
        unit = db.get(OrganizationUnit, pu.unit_id)
        unit_names.append({"unit_id": str(pu.unit_id), "name": unit.name if unit else "—"})
    open_blockers = int(db.scalar(select(func.count()).select_from(Blocker).where(
        Blocker.project_id == p.id, Blocker.status == BlockerStatus.open)) or 0)
    return {**_payload(db, p), "members": member_list, "units": unit_names,
            "milestones": [{"id": str(m.id), "title": m.title, "due_date": m.due_date.isoformat() if m.due_date else None,
                            "is_done": m.is_done, "description": m.description} for m in milestones],
            "open_blockers": open_blockers}


@router.put("/{project_id}")
def update_project(
    project_id: uuid.UUID, body: ProjectIn, request: Request,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "پروژه یافت نشد")
    is_pm = db.scalar(select(ProjectMember).where(
        ProjectMember.project_id == p.id, ProjectMember.user_id == actor.id,
        ProjectMember.role_in_project == "manager")) is not None
    if not (is_pm or _manageable(actor, db)):
        raise HTTPException(403, "مجوز ویرایش پروژه ندارید")
    for field, value in body.model_dump().items():
        setattr(p, field, value)
    p.version += 1
    audit(db, actor_id=actor.id, action="project_updated", entity_type="project", entity_id=p.id,
          summary=f"ویرایش پروژه {p.title}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, p)


@router.post("/{project_id}/members", status_code=201)
def add_member(
    project_id: uuid.UUID, body: dict, request: Request,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "پروژه یافت نشد")
    if not (is_project_manager(db, p, actor) or _manageable(actor, db)):
        raise HTTPException(403, "مجوز ندارید")
    uid = body.get("user_id")
    u = db.get(User, uuid.UUID(uid)) if uid else None
    if u is None:
        raise HTTPException(404, "کاربر یافت نشد")
    if db.scalar(select(ProjectMember).where(ProjectMember.project_id == p.id, ProjectMember.user_id == u.id)) is None:
        db.add(ProjectMember(project_id=p.id, user_id=u.id, role_in_project=body.get("role_in_project")))
    return {"ok": True}


def is_project_manager(db: OrmSession, p: Project, actor: User) -> bool:
    if p.manager_id == actor.id:
        return True
    return db.scalar(select(ProjectMember).where(
        ProjectMember.project_id == p.id, ProjectMember.user_id == actor.id,
        ProjectMember.role_in_project == "manager")) is not None


@router.delete("/{project_id}/members/{user_id}")
def remove_member(
    project_id: uuid.UUID, user_id: uuid.UUID, request: Request,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "پروژه یافت نشد")
    if not (is_project_manager(db, p, actor) or _manageable(actor, db)):
        raise HTTPException(403, "مجوز ندارید")
    from sqlalchemy import delete

    db.execute(delete(ProjectMember).where(ProjectMember.project_id == p.id, ProjectMember.user_id == user_id))
    audit(db, actor_id=actor.id, action="project_member_removed", entity_type="project", entity_id=p.id,
          summary=f"حذف عضو از پروژه {p.title}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    return {"ok": True}


@router.post("/{project_id}/milestones", status_code=201)
def add_milestone(
    project_id: uuid.UUID, body: dict, request: Request,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "پروژه یافت نشد")
    if not (is_project_manager(db, p, actor) or _manageable(actor, db)):
        raise HTTPException(403, "مجوز ندارید")
    m = Milestone(
        project_id=p.id, title=(body.get("title") or "").strip()[:200],
        description=body.get("description"),
        due_date=date.fromisoformat(body["due_date"]) if body.get("due_date") else None,
    )
    db.add(m)
    db.flush()
    return {"id": str(m.id), "title": m.title}


@router.get("/{project_id}/metrics")
def project_metrics(project_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    p = db.get(Project, project_id)
    if p is None or not can_view_project(db, actor, p):
        raise HTTPException(404, "پروژه یافت نشد")
    today = utcnow().date()
    year_start = today.replace(month=1, day=1)
    return {
        "progress": metrics.project_progress(db, p.id),
        "overdue_pct": metrics.overdue_pct(db, period_start=year_start, period_end=today, project_id=p.id),
        "on_time_current": metrics.on_time_pct(db, period_start=year_start, period_end=today, baseline="current", project_id=p.id),
        "on_time_base": metrics.on_time_pct(db, period_start=year_start, period_end=today, baseline="base", project_id=p.id),
        "delays": metrics.delay_stats(db, period_start=year_start, period_end=today, project_id=p.id),
    }
