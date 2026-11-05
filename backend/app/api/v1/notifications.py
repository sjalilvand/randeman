"""اعلان‌های درون‌سامانه (سند ۵.۷)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_current_user
from app.core.db import get_db
from app.models.base import utcnow
from app.models.ops import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False, page: int = 1, size: int = 30,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    conds = [Notification.user_id == actor.id]
    if unread_only:
        conds.append(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(Notification).where(*conds)) or 0
    unread = int(db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == actor.id, Notification.is_read.is_(False))) or 0)
    rows = db.execute(select(Notification).where(*conds).order_by(Notification.created_at.desc())
                      .offset((page - 1) * size).limit(size)).scalars().all()
    return {
        "items": [{"id": str(n.id), "type": n.type, "title": n.title, "body": n.body,
                   "entity_type": n.entity_type, "entity_id": str(n.entity_id) if n.entity_id else None,
                   "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in rows],
        "total": int(total), "unread": unread, "page": page, "size": size,
    }


class ReadIn(BaseModel):
    ids: list[uuid.UUID] = []


@router.post("/read")
def mark_read(body: ReadIn, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    rows = db.execute(select(Notification).where(Notification.user_id == actor.id,
                                                Notification.id.in_(body.ids))).scalars().all()
    for n in rows:
        n.is_read = True
        n.read_at = utcnow()
    return {"ok": True, "count": len(rows)}


@router.post("/read-all")
def mark_all_read(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    rows = db.execute(select(Notification).where(Notification.user_id == actor.id, Notification.is_read.is_(False))).scalars().all()
    for n in rows:
        n.is_read = True
        n.read_at = utcnow()
    return {"ok": True, "count": len(rows)}
