"""تقویم، ظرفیت، تعریف شاخص‌ها و تنظیمات (سند ۷، ۱۰.۲)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, ForeignKey, Numeric, String, Text, Uuid, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Holiday(Base, IdMixin):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("date", name="uq_holiday_date"),)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)


class UserCapacity(Base, IdMixin, TimestampMixin):
    __tablename__ = "user_capacities"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_capacity_user_week"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)


class WorkloadAllocation(Base, IdMixin, TimestampMixin):
    """تخصیص ساعات وظیفه به هفته/فرد — برای شاخص بار برنامه‌ریزی‌شده (سند ۷.۵)."""

    __tablename__ = "workload_allocations"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)


class MetricDefinition(Base, IdMixin, TimestampMixin):
    """فرمول و سیاست محاسبه شاخص‌ها — نسخه‌بندی‌شده (سند ۷)."""

    __tablename__ = "metric_definitions"

    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    title_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class MetricSnapshot(Base, IdMixin):
    __tablename__ = "metric_snapshots"

    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # org | unit | project | user
    scope_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    metric_key: Mapped[str] = mapped_column(String(60), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)  # None ⇒ غیرقابل محاسبه
    payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
