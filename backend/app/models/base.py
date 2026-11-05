"""پایه مدل‌ها: کلید UUID، زمان UTC، کنترل هم‌زمانی با version (سند ۱۰.۳ و ۱۰.۴)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Uuid, types
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(types.TypeDecorator):
    """ذخیره naive-UTC و بازگرداندن aware-UTC؛ سازگار روی PostgreSQL و SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):  # noqa: ANN001
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)


class VersionMixin:
    """به‌روزرسانی فقط با نسخه مورد انتظار؛ تعارض ⇒ 409 (سند ۱۰.۴)."""

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
