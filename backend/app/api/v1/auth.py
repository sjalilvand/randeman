"""احراز هویت — ورود، خروج، کاربر جاری، تغییر رمز (سند ۱۳.۱)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import (
    clear_session_cookie,
    create_session,
    ensure_not_locked,
    hash_password,
    register_failed_login,
    register_successful_login,
    revoke_session,
    session_from_request,
    set_session_cookie,
    verify_password,
)
from app.models.user import User
from app.services.audit_svc import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


def _user_payload(db: OrmSession, user: User) -> dict:
    from app.core.permissions import role_codes

    return {
        "id": str(user.id),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "position": user.position,
        "primary_unit_id": str(user.primary_unit_id) if user.primary_unit_id else None,
        "roles": sorted(role_codes(db, user)),
        "capacity_hours_per_week": user.capacity_hours_per_week,
    }


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: OrmSession = Depends(get_db)) -> dict:
    ip = get_actor_ip(request)
    user = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    generic = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="نام کاربری یا رمز عبور نادرست است")
    if user is None:
        raise generic
    if not user.is_active:
        raise HTTPException(status_code=403, detail="حساب غیرفعال است")
    ensure_not_locked(user)
    if not verify_password(user.password_hash, body.password):
        register_failed_login(db, user)
        audit(db, actor_id=user.id, action="login_failed", summary=f"ورود ناموفق برای {user.username}", ip=ip,
              user_agent=request.headers.get("user-agent"))
        db.commit()  # شمارنده تلاش ناموفق و ممیزی حتی در خطا ثبت شود
        raise generic
    register_successful_login(db, user)
    token = create_session(db, user, request)
    audit(db, actor_id=user.id, action="login", summary="ورود موفق", ip=ip,
          user_agent=request.headers.get("user-agent"))
    set_session_cookie(response, token)
    return {"user": _user_payload(db, user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: OrmSession = Depends(get_db)) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    found = session_from_request(db, request)
    if found is not None and token:
        revoke_session(db, token)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    return {"user": _user_payload(db, user)}


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: OrmSession = Depends(get_db),
) -> dict:
    if not verify_password(user.password_hash, body.old_password):
        raise HTTPException(status_code=422, detail="رمز فعلی نادرست است")
    if body.old_password == body.new_password:
        raise HTTPException(status_code=422, detail="رمز جدید باید متفاوت باشد")
    user.password_hash = hash_password(body.new_password)
    audit(db, actor_id=user.id, action="password_changed", entity_type="user", entity_id=user.id, summary="تغییر رمز")
    return {"ok": True}
