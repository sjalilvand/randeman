"""وابستگی‌های مشترک API — احراز هویت، نقش، و تضمین CSRF برای عملیات تغییردهنده."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from app.core.db import get_db
from app.core.security import session_from_request
from app.models.user import User

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def enforce_csrf(request: Request) -> None:
    """هم‌مبدأ + الزام سربرگ سفارشی ⇒ درخواست تغییردهندهٔ بین‌دامنه‌ای مسدود می‌شود."""
    if request.method in MUTATING_METHODS:
        if request.headers.get("x-requested-with") != "XMLHttpRequest":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="درخواست بدون نشان CSRF")


def get_current_user(request: Request, db: OrmSession = Depends(get_db)) -> User:
    enforce_csrf(request)
    found = session_from_request(db, request)
    if found is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ورود لازم است")
    return found[1]


def require_roles(*codes: str):
    """فقط نقش‌های مجاز (sys_admin همیشه عبور می‌کند)."""

    def checker(user: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> User:
        from app.core.permissions import role_codes

        roles = role_codes(db, user)
        if "sys_admin" in roles or (roles & set(codes)):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="مجوز کافی ندارید")

    return checker


def get_actor_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    trusted = getattr(request.app.state, "trusted_proxies", {"127.0.0.1"})
    if forwarded and request.client and request.client.host in trusted:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""
