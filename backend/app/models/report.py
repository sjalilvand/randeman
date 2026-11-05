"""گزارش هفتگی: نسخه‌بندی، اقلام و اقدامات بررسی (سند ۵.۵).

قاعده کلیدی: نسخه تأییدشده تصویر تاریخی است؛ تغییر بعدی رکوردها متن گزارش را عوض نمی‌کند.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime
from app.models.enums import ReportStatus, ReviewActionType

JSONType = JSON().with_variant(JSONB(), "postgresql")


class WeeklyReport(Base, IdMixin, TimestampMixin):
    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_report_user_week"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organization_units.id"), nullable=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # شنبه
    week_end: Mapped[date] = mapped_column(Date, nullable=False)                # جمعه

    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), nullable=False, default=ReportStatus.draft, index=True)
    version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False, default=1)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    blockers: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_requests: Mapped[str | None] = mapped_column(Text, nullable=True)

    approver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    submitted_late: Mapped[bool] = mapped_column(default=False, nullable=False)


class WeeklyReportItem(Base, IdMixin):
    __tablename__ = "weekly_report_items"

    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("weekly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tasks.id"), nullable=True)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("activities.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(30), nullable=True)  # done | ongoing | delay | unplanned


class WeeklyReportVersion(Base, IdMixin, TimestampMixin):
    """اسنپ‌شات تغییرناپذیر در هر ارسال/تأیید."""

    __tablename__ = "weekly_report_versions"

    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("weekly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ReviewAction(Base, IdMixin, TimestampMixin):
    __tablename__ = "review_actions"

    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("weekly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    action: Mapped[ReviewActionType] = mapped_column(Enum(ReviewActionType), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
