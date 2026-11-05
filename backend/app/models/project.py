"""پروژه‌ها، اعضا، نقاط عطف و اقلام قابل تحویل (سند ۵.۲)."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, VersionMixin
from app.models.enums import Confidentiality, DeliverableStatus, Priority, ProjectStatus


class Project(Base, IdMixin, TimestampMixin, VersionMixin):
    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sponsor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)
    lead_unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organization_units.id"), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.draft)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), nullable=False, default=Priority.medium)
    confidentiality: Mapped[Confidentiality] = mapped_column(
        Enum(Confidentiality), nullable=False, default=Confidentiality.internal
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_outputs: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_in_project: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ProjectUnit(Base):
    __tablename__ = "project_units"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organization_units.id", ondelete="CASCADE"), primary_key=True)
    participation_note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Milestone(Base, IdMixin, TimestampMixin):
    __tablename__ = "milestones"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_done: Mapped[bool] = mapped_column(default=False, nullable=False)


class Deliverable(Base, IdMixin, TimestampMixin):
    __tablename__ = "deliverables"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("milestones.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    status: Mapped[DeliverableStatus] = mapped_column(Enum(DeliverableStatus), nullable=False, default=DeliverableStatus.pending)
