"""مدیریت کاربران — فقط مدیر سامانه (سند ۴.۱ و ۴.۳)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user, require_roles
from app.core.db import get_db
from app.core.security import hash_password
from app.models.user import OrganizationUnit, Role, User, UserRole
from app.services.audit_svc import audit

router = APIRouter(prefix="/users", tags=["users"])


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    password: str | None = Field(default=None, min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    personnel_code: str | None = Field(default=None, max_length=40)
    position: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    primary_unit_id: uuid.UUID | None = None
    direct_manager_id: uuid.UUID | None = None
    capacity_hours_per_week: float | None = Field(default=None, gt=0, le=80)
    work_start_date: date | None = None
    roles: list[str] = []


def _get_role_ids(db: OrmSession, codes: list[str]) -> list[uuid.UUID]:
    return list(db.execute(select(Role.id).where(Role.code.in_(codes))).scalars().all())


def _payload(db: OrmSession, u: User) -> dict:
    from app.core.permissions import role_codes

    unit = db.get(OrganizationUnit, u.primary_unit_id) if u.primary_unit_id else None
    mgr = db.get(User, u.direct_manager_id) if u.direct_manager_id else None
    return {
        "id": str(u.id), "username": u.username, "first_name": u.first_name, "last_name": u.last_name,
        "full_name": u.full_name, "personnel_code": u.personnel_code, "position": u.position,
        "email": u.email, "phone": u.phone, "is_active": u.is_active,
        "work_start_date": u.work_start_date.isoformat() if u.work_start_date else None,
        "capacity_hours_per_week": u.capacity_hours_per_week,
        "primary_unit_id": str(u.primary_unit_id) if u.primary_unit_id else None,
        "primary_unit_name": unit.name if unit else None,
        "direct_manager_id": str(u.direct_manager_id) if u.direct_manager_id else None,
        "direct_manager_name": mgr.full_name if mgr else None,
        "roles": sorted(role_codes(db, u)),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@router.get("")
def list_users(
    q: str | None = None, unit_id: uuid.UUID | None = None, active: bool | None = None,
    page: int = 1, size: int = 20,
    user: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(User.first_name.ilike(like), User.last_name.ilike(like), User.username.ilike(like)))
    if unit_id:
        conds.append(User.primary_unit_id == unit_id)
    if active is not None:
        conds.append(User.is_active == active)
    total = db.scalar(select(func.count()).select_from(User).where(*conds)) or 0
    rows = db.execute(
        select(User).where(*conds).order_by(User.last_name).offset((page - 1) * size).limit(size)
    ).scalars().all()
    return {"items": [_payload(db, u) for u in rows], "total": int(total), "page": page, "size": size}


@router.post("", status_code=201)
def create_user(
    body: UserIn,
    request: Request,
    actor: User = Depends(require_roles()),
    db: OrmSession = Depends(get_db),
) -> dict:
    if not body.password:
        raise HTTPException(422, "رمز اولیه الزامی است")
    if db.scalar(select(User).where(User.username == body.username)) is not None:
        raise HTTPException(422, "نام کاربری تکراری است")
    u = User(
        username=body.username.strip().lower(),
        password_hash=hash_password(body.password),
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        personnel_code=body.personnel_code,
        position=body.position,
        email=body.email,
        phone=body.phone,
        primary_unit_id=body.primary_unit_id,
        direct_manager_id=body.direct_manager_id,
        capacity_hours_per_week=body.capacity_hours_per_week,
        work_start_date=body.work_start_date,
    )
    db.add(u)
    db.flush()
    for rid in _get_role_ids(db, body.roles):
        db.add(UserRole(user_id=u.id, role_id=rid))
    audit(db, actor_id=actor.id, action="user_created", entity_type="user", entity_id=u.id,
          summary=f"ایجاد کاربر {u.username}", detail={"roles": body.roles},
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, u)


@router.get("/{user_id}")
def get_user(user_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "کاربر یافت نشد")
    return _payload(db, u)


@router.put("/{user_id}")
def update_user(
    user_id: uuid.UUID, body: UserIn, request: Request,
    actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db),
) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "کاربر یافت نشد")
    changed_roles = body.roles is not None
    old_roles = [] if not changed_roles else sorted(
        db.execute(select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == u.id)).scalars().all()
    )
    u.first_name, u.last_name = body.first_name.strip(), body.last_name.strip()
    u.personnel_code, u.position, u.email, u.phone = body.personnel_code, body.position, body.email, body.phone
    u.primary_unit_id, u.direct_manager_id = body.primary_unit_id, body.direct_manager_id
    u.capacity_hours_per_week, u.work_start_date = body.capacity_hours_per_week, body.work_start_date
    if body.password:
        u.password_hash = hash_password(body.password)
    if changed_roles:
        from sqlalchemy import delete

        db.execute(delete(UserRole).where(UserRole.user_id == u.id))
        for rid in _get_role_ids(db, body.roles):
            db.add(UserRole(user_id=u.id, role_id=rid))
    audit(db, actor_id=actor.id, action="user_updated", entity_type="user", entity_id=u.id,
          summary=f"ویرایش کاربر {u.username}", detail={"roles_changed": changed_roles, "old_roles": old_roles},
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, u)


@router.post("/{user_id}/deactivate")
def deactivate(
    user_id: uuid.UUID, request: Request,
    actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db),
) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "کاربر یافت نشد")
    u.is_active = False
    audit(db, actor_id=actor.id, action="user_deactivated", entity_type="user", entity_id=u.id,
          summary=f"غیرفعال‌سازی {u.username} — سوابق تاریخی حفظ می‌شود",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    return {"ok": True}


@router.post("/{user_id}/activate")
def activate(
    user_id: uuid.UUID, request: Request,
    actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db),
) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "کاربر یافت نشد")
    u.is_active = True
    audit(db, actor_id=actor.id, action="user_activated", entity_type="user", entity_id=u.id,
          summary=f"فعال‌سازی {u.username}", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    return {"ok": True}
