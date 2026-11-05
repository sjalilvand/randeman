"""وظایف: گردش وضعیت، تاریخچه، وابستگی‌ها و درخواست تغییر (سند ۵.۳)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime, VersionMixin
from app.models.enums import ChangeRequestStatus, Complexity, Priority, TaskStatus


class Task(Base, IdMixin, TimestampMixin, VersionMixin):
    __tablename__ = "tasks"

    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=True, index=True)
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("milestones.id"), nullable=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organization_units.id"), nullable=True, index=True)

    assignee_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)  # مسئول اصلی
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)

    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    base_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)     # سررسید مبنا — حفظ می‌شود
    current_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # سررسید جاری مصوب
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    priority: Mapped[Priority] = mapped_column(Enum(Priority), nullable=False, default=Priority.medium)
    complexity: Mapped[Complexity] = mapped_column(Enum(Complexity), nullable=False, default=Complexity.medium)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.draft, index=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_documents: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class TaskCollaborator(Base):
    __tablename__ = "task_collaborators"

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)


class TaskStatusHistory(Base, IdMixin, TimestampMixin):
    __tablename__ = "task_status_history"

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskChangeLog(Base, IdMixin, TimestampMixin):
    """تاریخچه تغییر مهلت، مسئول، وزن و معیار پذیرش (سند ۵.۳ قواعد)."""

    __tablename__ = "task_change_logs"

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class TaskChangeRequest(Base, IdMixin, TimestampMixin):
    """درخواست تغییر سررسید — تصویب، سررسید جاری را تغییر می‌دهد؛ سررسید مبنا ثابت می‌ماند."""

    __tablename__ = "task_change_requests"

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    field: Mapped[str] = mapped_column(String(40), nullable=False, default="current_due_date")
    old_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(500), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ChangeRequestStatus] = mapped_column(Enum(ChangeRequestStatus), nullable=False, default=ChangeRequestStatus.pending)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
