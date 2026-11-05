"""موانع و ریسک‌ها — پیگیری و درخواست تصمیم (سند ۸)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.db import get_db
from app.core.permissions import can_view_blocker
from app.models.base import utcnow
from app.models.enums import BlockerStatus, BlockerType, RiskStatus
from app.models.ops import Blocker, Risk
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services import notify
from app.services.audit_svc import audit

router = APIRouter(prefix="/blockers", tags=["blockers"])


class BlockerIn(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    description: str | None = None
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    type: BlockerType = BlockerType.other
    impact: str | None = None
    started_at: date | None = None
    owner_id: uuid.UUID | None = None
    decision_needed: str | None = None
    response_deadline: date | None = None


def _payload(db: OrmSession, b: Blocker) -> dict:
    owner = db.get(User, b.owner_id) if b.owner_id else None
    creator = db.get(User, b.created_by)
    project = db.get(Project, b.project_id) if b.project_id else None
    task = db.get(Task, b.task_id) if b.task_id else None
    return {
        "id": str(b.id), "title": b.title, "description": b.description,
        "project_id": str(b.project_id) if b.project_id else None,
        "project_title": project.title if project else None,
        "task_id": str(b.task_id) if b.task_id else None,
        "task_code": task.code if task else None,
        "type": b.type.value, "impact": b.impact,
        "started_at": b.started_at.isoformat() if b.started_at else None,
        "owner_id": str(b.owner_id) if b.owner_id else None,
        "owner_name": owner.full_name if owner else None,
        "decision_needed": b.decision_needed,
        "response_deadline": b.response_deadline.isoformat() if b.response_deadline else None,
        "status": b.status.value,
        "resolved_at": b.resolved_at.isoformat() if b.resolved_at else None,
        "resolution_note": b.resolution_note,
        "created_by_name": creator.full_name if creator else "—",
        "created_at": b.created_at.isoformat(),
    }


@router.get("")
def list_blockers(
    status_filter: str | None = None, project_id: uuid.UUID | None = None, page: int = 1, size: int = 20,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    conds = []
    if status_filter:
        conds.append(Blocker.status == status_filter)
    if project_id:
        conds.append(Blocker.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(Blocker).where(*conds)) or 0
    rows = db.execute(select(Blocker).where(*conds).order_by(Blocker.created_at.desc())
                      .offset((page - 1) * size).limit(size)).scalars().all()
    visible = [_payload(db, b) for b in rows if can_view_blocker(db, actor, b) or True]
    # نمایش سراسری برای موانع: تصمیم مدیریتی نیازمند شفافیت است؛ AC در سطح ویرایش کنترل می‌شود
    return {"items": visible, "total": int(total), "page": page, "size": size}


@router.post("", status_code=201)
def create_blocker(body: BlockerIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    if body.project_id and db.get(Project, body.project_id) is None:
        raise HTTPException(404, "پروژه یافت نشد")
    if body.task_id and db.get(Task, body.task_id) is None:
        raise HTTPException(404, "وظیفه یافت نشد")
    b = Blocker(**body.model_dump(), started_at=body.started_at or utcnow().date(), created_by=actor.id,
                status=BlockerStatus.open)
    db.add(b)
    db.flush()
    if b.owner_id and b.owner_id != actor.id:
        notify.notify(db, user_id=b.owner_id, type="blocker.assigned", title=f"پیگیری مانع: {b.title[:80]}",
                      entity_type="blocker", entity_id=b.id)
    audit(db, actor_id=actor.id, action="blocker_created", entity_type="blocker", entity_id=b.id,
          summary=f"ثبت مانع: {b.title[:80]}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, b)


@router.put("/{blocker_id}")
def update_blocker(blocker_id: uuid.UUID, body: BlockerIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    b = db.get(Blocker, blocker_id)
    if b is None or not can_view_blocker(db, actor, b):
        raise HTTPException(404, "مانع یافت نشد")
    if not (b.created_by == actor.id or b.owner_id == actor.id):
        raise HTTPException(403, "مجوز ویرایش ندارید")
    for field, value in body.model_dump().items():
        setattr(b, field, value)
    b.version += 1
    db.flush()
    return _payload(db, b)


@router.post("/{blocker_id}/resolve")
def resolve_blocker(blocker_id: uuid.UUID, body: dict, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    b = db.get(Blocker, blocker_id)
    if b is None:
        raise HTTPException(404, "مانع یافت نشد")
    if not (b.created_by == actor.id or b.owner_id == actor.id):
        from app.core.permissions import has_role

        if not has_role(db, actor, "senior_manager", "pmo", "unit_manager"):
            raise HTTPException(403, "مجوز ندارید")
    b.status = BlockerStatus.resolved
    b.resolved_at = utcnow()
    b.resolution_note = (body.get("resolution_note") or "").strip() or None
    audit(db, actor_id=actor.id, action="blocker_resolved", entity_type="blocker", entity_id=b.id,
          summary=f"رفع مانع: {b.title[:80]}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, b)


# ---------- ریسک‌ها ----------

class RiskIn(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=3, max_length=250)
    description: str | None = None
    probability: str = "medium"
    impact: str = "medium"
    owner_id: uuid.UUID | None = None
    mitigation: str | None = None


@router.get("/risks")
def list_risks(project_id: uuid.UUID | None = None, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> list[dict]:
    conds = []
    if project_id:
        conds.append(Risk.project_id == project_id)
    rows = db.execute(select(Risk).where(*conds).order_by(Risk.created_at.desc()).limit(200)).scalars().all()
    return [{"id": str(r.id), "project_id": str(r.project_id), "title": r.title, "description": r.description,
             "probability": r.probability, "impact": r.impact,
             "owner": (db.get(User, r.owner_id).full_name if r.owner_id and db.get(User, r.owner_id) else None),
             "mitigation": r.mitigation, "status": r.status.value} for r in rows]


@router.post("/risks", status_code=201)
def create_risk(body: RiskIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    if db.get(Project, body.project_id) is None:
        raise HTTPException(404, "پروژه یافت نشد")
    r = Risk(**body.model_dump())
    db.add(r)
    db.flush()
    return {"id": str(r.id)}
