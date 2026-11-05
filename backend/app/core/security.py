"""امنیت: هش رمز Argon2id، نشست سرور-سمت و محدودیت تلاش ناموفق (سند ۱۳.۱)."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select, update

from app.core.config import settings
from app.models.base import utcnow
from app.models.ops import Session
from app.models.user import User

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    try:
        _ph.verify(password_hash, plain)
        return True
    except (VerifyMismatchError, ValueError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, user: User, request: Request) -> str:  # noqa: ANN001
    token = new_token()
    db.add(
        Session(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(minutes=settings.session_ttl_minutes),
            ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:255],
        )
    )
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


def register_failed_login(db, user: User) -> None:  # noqa: ANN001
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= settings.login_max_failed:
        user.locked_until = utcnow() + timedelta(minutes=settings.login_lock_minutes)


def register_successful_login(db, user: User) -> None:  # noqa: ANN001
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()


def revoke_session(db, token: str) -> None:  # noqa: ANN001
    db.execute(
        update(Session)
        .where(Session.token_hash == token_hash(token), Session.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def session_from_request(db, request: Request) -> tuple[Session, User] | None:  # noqa: ANN001
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    sess = db.scalar(select(Session).where(Session.token_hash == token_hash(token)))
    if sess is None or sess.revoked_at is not None or sess.expires_at < utcnow():
        return None
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        return None
    return sess, user


def ensure_not_locked(user: User) -> None:
    if user.locked_until and user.locked_until > utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="حساب به دلیل تلاش‌های ناموفق موقتاً قفل است؛ بعداً تلاش کنید.",
        )


__all__ = [
    "clear_session_cookie", "create_session", "ensure_not_locked", "hash_password",
    "new_token", "register_failed_login", "register_successful_login", "revoke_session",
    "session_from_request", "set_session_cookie", "token_hash", "verify_password",
]
