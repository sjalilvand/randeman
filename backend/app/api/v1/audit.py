"""ممیزی: مشاهده رویدادها در محدوده مجاز (سند ۴.۱ و ۱۰.۲)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_current_user
from app.core.db import get_db
from app.core.permissions import has_role
from app.models.ops import AuditEvent
from app.models.user import User

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("")
def list_audit(
    entity_type: str | None = None, entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None, action: str | None = None,
    page: int = 1, size: int = 30,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    if not has_role(db, actor, "auditor", "senior_manager", "pmo"):
        # کاربر عادی فقط سوابق عملیات خودش (سند ۴.۳)
        if actor_id and actor_id != actor.id:
            return {"items": [], "total": 0, "page": page, "size": size}
        actor_id = actor.id
    conds = []
    if entity_type:
        conds.append(AuditEvent.entity_type == entity_type)
    if entity_id:
        conds.append(AuditEvent.entity_id == entity_id)
    if actor_id:
        conds.append(AuditEvent.actor_id == actor_id)
    if action:
        conds.append(AuditEvent.action == action)
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conds)) or 0
    rows = db.execute(select(AuditEvent).where(*conds).order_by(AuditEvent.created_at.desc())
                      .offset((page - 1) * size).limit(size)).scalars().all()
    return {"items": [{
        "id": str(a.id), "action": a.action,
        "actor_name": (db.get(User, a.actor_id).full_name if a.actor_id and db.get(User, a.actor_id) else "—"),
        "entity_type": a.entity_type, "entity_id": str(a.entity_id) if a.entity_id else None,
        "summary": a.summary, "detail": a.detail, "ip": a.ip,
        "created_at": a.created_at.isoformat(),
    } for a in rows], "total": int(total), "page": page, "size": size}
