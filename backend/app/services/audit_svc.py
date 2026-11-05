"""سرویس ممیزی: ثبت رویدادهای حساس (سند ۴.۳ و ۱۳.۲)."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as OrmSession

from app.models.base import utcnow
from app.models.ops import AuditEvent


def audit(
    db: OrmSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    summary: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=(summary or "")[:500] or None,
            detail=detail,
            ip=(ip or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
        )
    )


def heartbeat(db: OrmSession) -> None:  # noqa: ARG001 — نگه‌داری برای سازگاری آتی
    """ضربان Worker در system_settings ثبت می‌شود (app.worker)."""
    _ = utcnow()
