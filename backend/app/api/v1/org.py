"""ساختار سازمانی: واحدها، زیرواحدها، مدیر و جانشین (سند ۵.۱)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user, require_roles
from app.core.db import get_db
from app.models.user import OrganizationUnit, User
from app.services.audit_svc import audit

router = APIRouter(prefix="/organization-units", tags=["organization-units"])


class UnitIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, max_length=40)
    parent_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    deputy_manager_id: uuid.UUID | None = None
    description: str | None = None


def _payload(db: OrmSession, u: OrganizationUnit) -> dict:
    mgr = db.get(User, u.manager_id) if u.manager_id else None
    deputy = db.get(User, u.deputy_manager_id) if u.deputy_manager_id else None
    children = db.execute(select(OrganizationUnit.id).where(OrganizationUnit.parent_id == u.id)).scalars().all()
    return {
        "id": str(u.id), "name": u.name, "code": u.code,
        "parent_id": str(u.parent_id) if u.parent_id else None,
        "manager_id": str(u.manager_id) if u.manager_id else None,
        "manager_name": mgr.full_name if mgr else None,
        "deputy_manager_id": str(u.deputy_manager_id) if u.deputy_manager_id else None,
        "deputy_manager_name": deputy.full_name if deputy else None,
        "is_active": u.is_active, "description": u.description,
        "children_count": len(children),
    }


@router.get("")
def list_units(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(OrganizationUnit).order_by(OrganizationUnit.name)).scalars().all()
    return [_payload(db, u) for u in rows]


@router.get("/tree")
def unit_tree(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(OrganizationUnit).order_by(OrganizationUnit.name)).scalars().all()
    by_parent: dict[uuid.UUID | None, list[OrganizationUnit]] = {}
    for u in rows:
        by_parent.setdefault(u.parent_id, []).append(u)

    def node(u: OrganizationUnit) -> dict:
        return {**_payload(db, u), "children": [node(c) for c in by_parent.get(u.id, [])]}

    return [node(r) for r in by_parent.get(None, [])]


@router.post("", status_code=201)
def create_unit(
    body: UnitIn, request: Request,
    actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db),
) -> dict:
    if body.parent_id and db.get(OrganizationUnit, body.parent_id) is None:
        raise HTTPException(404, "واحد والد یافت نشد")
    if body.manager_id and db.get(User, body.manager_id) is None:
        raise HTTPException(404, "مدیر انتخابی یافت نشد")
    u = OrganizationUnit(**body.model_dump())
    db.add(u)
    db.flush()
    audit(db, actor_id=actor.id, action="unit_created", entity_type="organization_unit", entity_id=u.id,
          summary=f"ایجاد واحد {u.name}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, u)


@router.put("/{unit_id}")
def update_unit(
    unit_id: uuid.UUID, body: UnitIn, request: Request,
    actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db),
) -> dict:
    u = db.get(OrganizationUnit, unit_id)
    if u is None:
        raise HTTPException(404, "واحد یافت نشد")
    if body.parent_id == u.id:
        raise HTTPException(422, "واحد نمی‌تواند والد خودش باشد")
    for field, value in body.model_dump().items():
        setattr(u, field, value)
    audit(db, actor_id=actor.id, action="unit_updated", entity_type="organization_unit", entity_id=u.id,
          summary=f"ویرایش واحد {u.name}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, u)
