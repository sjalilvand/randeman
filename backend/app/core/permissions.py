"""کنترل دسترسی رکوردی (سند ۴.۲) — مجوز مؤثر = نقش + محدوده سازمانی + عضویت پروژه.

کنترل در FastAPI و سطح رکورد اجرا می‌شود؛ پنهان‌کردن دکمه در رابط کافی نیست.
رکورد غیرمجاز با 404 پاس داده می‌شود تا حتی وجودش افشا نشود.
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.activity import Activity
from app.models.ops import Blocker
from app.models.project import Project, ProjectMember
from app.models.report import WeeklyReport
from app.models.task import Task, TaskCollaborator
from app.models.user import OrganizationUnit, Role, User, UserRole

ORG_WIDE_READ_ROLES = {"senior_manager", "pmo", "observer", "auditor"}
MANAGE_ROLES = {"senior_manager", "pmo"}


def role_codes(db, user: User) -> set[str]:  # noqa: ANN001
    rows = db.execute(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    ).scalars().all()
    codes = set(rows)
    return codes


def has_role(db, user: User, *codes: str) -> bool:  # noqa: ANN001
    if user.is_active is False:
        return False
    roles = role_codes(db, user)
    return bool(roles & set(codes)) or "sys_admin" in roles


def is_sys_admin(db, user: User) -> bool:  # noqa: ANN001
    return "sys_admin" in role_codes(db, user)


def descendant_unit_ids(db, unit_ids: set[uuid.UUID]) -> set[uuid.UUID]:  # noqa: ANN001
    """زیرشاخه واحدها — برای محدوده مدیر واحد."""
    if not unit_ids:
        return set()
    rows = db.execute(select(OrganizationUnit.id, OrganizationUnit.parent_id)).all()
    children: dict[uuid.UUID | None, set[uuid.UUID]] = {}
    for uid, pid in rows:
        children.setdefault(pid, set()).add(uid)
    result: set[uuid.UUID] = set()
    stack = list(unit_ids)
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(children.get(current, ()))
    return result


def managed_unit_ids(db, user: User) -> set[uuid.UUID]:  # noqa: ANN001
    rows = db.execute(
        select(OrganizationUnit.id).where(
            or_(OrganizationUnit.manager_id == user.id, OrganizationUnit.deputy_manager_id == user.id)
        )
    ).scalars().all()
    return descendant_unit_ids(db, set(rows))


def member_project_ids(db, user: User) -> set[uuid.UUID]:  # noqa: ANN001
    rows = db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)).scalars().all()
    return set(rows)


def _membership_conds(db, user: User) -> list[ColumnElement[bool]]:  # noqa: ANN001
    conds: list[ColumnElement[bool]] = [
        Task.assignee_id == user.id,
        Task.created_by == user.id,
        Task.approver_id == user.id,
        Task.id.in_(select(TaskCollaborator.task_id).where(TaskCollaborator.user_id == user.id)),
    ]
    pids = member_project_ids(db, user)
    if pids:
        conds.append(Task.project_id.in_(pids))
    uids = managed_unit_ids(db, user)
    if uids:
        conds.append(Task.unit_id.in_(uids))
    return conds


def task_visibility_filter(db, user: User) -> list[ColumnElement[bool]] | None:  # noqa: ANN001
    """None یعنی بدون محدودیت (نقش سازمانی)."""
    if has_role(db, user, *ORG_WIDE_READ_ROLES):
        return None
    return _membership_conds(db, user)


def can_view_task(db, user: User, task: Task) -> bool:  # noqa: ANN001
    flt = task_visibility_filter(db, user)
    if flt is None:
        return True
    return db.scalar(select(Task.id).where(Task.id == task.id, or_(*flt))) is not None


def can_manage_task(db, user: User, task: Task) -> bool:
    """ایجاد/ویرایش وظیفه: مدیر واحد، مدیر پروژه، PMO/مدیر ارشد یا ایجادکننده."""
    if has_role(db, user, "senior_manager", "pmo"):
        return True
    if task.created_by == user.id:
        return True
    if task.project_id and db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == task.project_id,
            ProjectMember.user_id == user.id,
            ProjectMember.role_in_project == "manager",
        )
    ):
        return True
    if task.unit_id and task.unit_id in managed_unit_ids(db, user):
        return True
    return False


def can_review_task(db, user: User, task: Task) -> bool:
    """تأیید/اصلاح خروجی: تأییدکننده تعیین‌شده، مدیر واحد، مدیر پروژه، PMO/مدیر ارشد."""
    if task.approver_id == user.id:
        return True
    return has_role(db, user, "senior_manager", "pmo") or can_manage_task(db, user, task)


def project_visibility_filter(db, user: User) -> list[ColumnElement[bool]] | None:  # noqa: ANN001
    if has_role(db, user, *ORG_WIDE_READ_ROLES):
        return None
    pids = member_project_ids(db, user)
    conds: list[ColumnElement[bool]] = [Project.created_by == user.id]
    if pids:
        conds.append(Project.id.in_(pids))
    # کارمندِ واحدِ راهبر یا مشارکت‌کننده هم می‌تواند پروژه فعال را ببیند
    my_units = {user.primary_unit_id} if user.primary_unit_id else set()
    if my_units:
        conds.append(Project.lead_unit_id.in_(my_units))
    conds.append(Project.status != "draft")
    return conds


def can_view_project(db, user: User, project: Project) -> bool:  # noqa: ANN001
    flt = project_visibility_filter(db, user)
    if flt is None:
        return True
    return db.scalar(select(Project.id).where(Project.id == project.id, or_(*flt))) is not None


def report_visibility_filter(db, user: User) -> list[ColumnElement[bool]] | None:  # noqa: ANN001
    if has_role(db, user, "senior_manager", "pmo", "auditor"):
        return None
    conds: list[ColumnElement[bool]] = [WeeklyReport.user_id == user.id, WeeklyReport.approver_id == user.id]
    uids = managed_unit_ids(db, user)
    if uids:
        conds.append(WeeklyReport.unit_id.in_(uids))
    return conds


def can_view_report(db, user: User, report: WeeklyReport) -> bool:  # noqa: ANN001
    flt = report_visibility_filter(db, user)
    if flt is None:
        return True
    return db.scalar(select(WeeklyReport.id).where(WeeklyReport.id == report.id, or_(*flt))) is not None


def can_review_report(db, user: User, report: WeeklyReport) -> bool:  # noqa: ANN001
    if report.user_id == user.id:
        return False  # تأیید گزارش توسط صاحب گزارش ممنوع (سند ۴.۳)
    if report.approver_id == user.id:
        return True
    if report.unit_id and report.unit_id in managed_unit_ids(db, user):
        return True
    return has_role(db, user, "senior_manager", "pmo")


def can_view_activity(db, user: User, activity: Activity) -> bool:  # noqa: ANN001
    if activity.user_id == user.id or has_role(db, user, *ORG_WIDE_READ_ROLES):
        return True
    uids = managed_unit_ids(db, user)
    return bool(uids) and db.scalar(
        select(User.id).where(User.id == activity.user_id, or_(User.primary_unit_id.in_(uids)))
    ) is not None


def can_view_blocker(db, user: User, blocker: Blocker) -> bool:  # noqa: ANN001
    if has_role(db, user, *ORG_WIDE_READ_ROLES):
        return True
    if blocker.created_by == user.id or blocker.owner_id == user.id:
        return True
    if blocker.project_id:
        return blocker.project_id in member_project_ids(db, user) or _is_unit_member_of_project(db, user, blocker.project_id)
    return False


def _is_unit_member_of_project(db, user: User, project_id: uuid.UUID) -> bool:  # noqa: ANN001
    from sqlalchemy import exists

    pu = select(ProjectUnit.project_id).where(ProjectUnit.project_id == project_id)
    return bool(user.primary_unit_id) and db.scalar(
        select(exists().where(pu.where(ProjectUnit.unit_id == user.primary_unit_id).subquery().select()))
    ) is not None or False


def visible_document_conds(db, user: User) -> list:  # noqa: ANN001
    """شرایط دیدن مستند: بارگذارنده، نقش سازمانی، یا عضویت در پروژه/واحد مرتبط."""
    from app.models.document import Document, DocumentLink

    if has_role(db, user, *ORG_WIDE_READ_ROLES):
        return [Document.uploaded_by == Document.uploaded_by]
    conds = [Document.uploaded_by == user.id]
    pids = member_project_ids(db, user)
    if pids:
        conds.append(
            Document.id.in_(
                select(DocumentLink.document_id).where(
                    DocumentLink.entity_type == "project", DocumentLink.entity_id.in_(pids)
                )
            )
        )
    return conds
