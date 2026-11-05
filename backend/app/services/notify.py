"""اعلان و رویداد خروجی — ثبت اتمی در همان تراکنش رویداد (سند ۵.۷ و ۱۱.۳)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.models.base import utcnow
from app.models.enums import OutboxStatus
from app.models.ops import Notification, OutboxEvent


def notify(
    db: OrmSession,
    *,
    user_id: uuid.UUID,
    type: str,  # noqa: A002 — نام دامنه
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> None:
    """ایجاد اعلان داخلی + رویداد خروجی قابل رهگیری (ایمیل در Worker، وابسته به SMTP)."""
    db.add(
        Notification(
            user_id=user_id,
            type=type,
            title=title[:250],
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )
    db.add(
        OutboxEvent(
            type="notification.created",
            payload={
                "notification_type": type,
                "user_id": str(user_id),
                "title": title,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id else None,
            },
        )
    )


def process_outbox(db: OrmSession, limit: int = 50) -> int:
    """پردازش رویدادهای خروجی — در MVP علامت‌گذاری پردازش‌شده؛ کانال ایمیل توسعه آتی."""
    events = db.execute(
        select(OutboxEvent).where(OutboxEvent.status == OutboxStatus.pending).limit(limit)
    ).scalars().all()
    for ev in events:
        ev.status = OutboxStatus.processed
        ev.processed_at = utcnow()
        ev.attempts = (ev.attempts or 0) + 1
    if events:
        db.commit()
    return len(events)
