"""هویت، نقش‌ها و ساختار سازمانی (سند ۵.۱ و ۴)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, UTCDateTime


class Role(Base, IdMixin, TimestampMixin):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    personnel_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    work_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    capacity_hours_per_week: Mapped[float | None] = mapped_column(nullable=True)  # خالی ⇒ مقدار پیش‌فرض سامانه
    direct_manager_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    primary_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organization_units.id", use_alter=True), nullable=True
    )

    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    # محدوده اختیاری نقش (مثلاً مدیر واحد فقط برای یک واحد) — برای توسعه آتی
    scope_unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organization_units.id"), nullable=True)


class OrganizationUnit(Base, IdMixin, TimestampMixin):
    __tablename__ = "organization_units"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organization_units.id"), nullable=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", use_alter=True), nullable=True)
    deputy_manager_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", use_alter=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserUnitAssignment(Base, IdMixin):
    """تاریخچه عضویت در واحدها — انتقال فعلی، گزارش‌های گذشته را جابه‌جا نمی‌کند (سند ۵.۱)."""

    __tablename__ = "user_unit_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organization_units.id"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
