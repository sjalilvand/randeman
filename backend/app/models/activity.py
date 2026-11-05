"""فعالیت: اقدام انجام‌شده، مستقل از وظیفه (سند ۵.۴)."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, VersionMixin
from app.models.enums import ActivityType


class Activity(Base, IdMixin, TimestampMixin, VersionMixin):
    __tablename__ = "activities"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tasks.id"), nullable=True, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # غیرمنفی؛ نامعتبر رد می‌شود
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), nullable=False, default=ActivityType.execution)
    blocker_note: Mapped[str | None] = mapped_column(Text, nullable=True)
