"""منطق دامنه وظایف — انتقال وضعیت، تاریخچه، وابستگی و درخواست تغییر (سند ۵.۳)."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.models.base import utcnow
from app.models.enums import TaskStatus
from app.models.ops import Blocker, BlockerStatus, BlockerType
from app.models.task import Task, TaskChangeLog, TaskChangeRequest, TaskDependency, TaskStatusHistory
from app.models.user import User

# جدول انتقال‌های مجاز — مطابق سند ۵.۳
TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.draft: {TaskStatus.assigned, TaskStatus.cancelled},
    TaskStatus.assigned: {TaskStatus.in_progress, TaskStatus.cancelled},
    TaskStatus.in_progress: {TaskStatus.ready_for_review, TaskStatus.blocked, TaskStatus.cancelled},
    TaskStatus.ready_for_review: {TaskStatus.completed, TaskStatus.needs_correction},
    TaskStatus.needs_correction: {TaskStatus.in_progress},
    TaskStatus.blocked: {TaskStatus.in_progress, TaskStatus.cancelled},
    # completed و cancelled وضعیت نهایی‌اند؛ بازگشایی «عملیات ثبت‌شده» است نه انتقال مستقیم
}

FINAL_STATUSES = {TaskStatus.completed, TaskStatus.cancelled}


def transition(
    db: OrmSession,
    *,
    task: Task,
    to_status: TaskStatus,
    actor: User,
    reason: str | None = None,
) -> None:
    if to_status not in TRANSITIONS.get(task.status, set()):
        raise HTTPException(status_code=422, detail=f"انتقال از «{task.status.value}» به «{to_status.value}» مجاز نیست")
    from_status = task.status
    task.status = to_status
    db.add(
        TaskStatusHistory(task_id=task.id, from_status=from_status.value, to_status=to_status.value,
                          actor_id=actor.id, reason=reason)
    )


def reopen(db: OrmSession, *, task: Task, actor: User, reason: str) -> None:
    """«بازگشایی» عملیاتی ثبت‌شده با مجوز و دلیل (سند ۵.۳)."""
    if task.status != TaskStatus.completed:
        raise HTTPException(status_code=422, detail="فقط وظیفه تکمیل و تأییدشده قابل بازگشایی است")
    if not reason or len(reason.strip()) < 5:
        raise HTTPException(status_code=422, detail="ثبت دلیل برای بازگشایی الزامی است")
    task.status = TaskStatus.in_progress
    task.completed_at = None
    task.submitted_at = None
    db.add(TaskStatusHistory(task_id=task.id, from_status=TaskStatus.completed.value,
                             to_status=TaskStatus.in_progress.value, actor_id=actor.id, reason=reason))


def ensure_no_cycle(db: OrmSession, *, task_id: uuid.UUID, depends_on: uuid.UUID) -> None:
    """وابستگی‌ها نباید چرخه ایجاد کنند."""
    if task_id == depends_on:
        raise HTTPException(status_code=422, detail="وظیفه نمی‌تواند به خودش وابسته باشد")
    seen: set[uuid.UUID] = set()
    stack = [depends_on]
    while stack:
        current = stack.pop()
        if current == task_id:
            raise HTTPException(status_code=422, detail="این وابستگی چرخه ایجاد می‌کند")
        if current in seen:
            continue
        seen.add(current)
        deps = db.execute(select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == current)).scalars().all()
        stack.extend(deps)


def add_dependency(db: OrmSession, *, task: Task, depends_on_task_id: uuid.UUID) -> None:
    target = db.get(Task, depends_on_task_id)
    if target is None:
        raise HTTPException(status_code=404, detail="وظیفه مبنای وابستگی یافت نشد")
    ensure_no_cycle(db, task_id=task.id, depends_on=depends_on_task_id)
    exists = db.scalar(
        select(TaskDependency).where(TaskDependency.task_id == task.id, TaskDependency.depends_on_task_id == depends_on_task_id)
    )
    if exists is None:
        db.add(TaskDependency(task_id=task.id, depends_on_task_id=depends_on_task_id))


def log_change(db: OrmSession, *, task: Task, field: str, old, new, actor: User, reason: str | None = None) -> None:
    db.add(TaskChangeLog(task_id=task.id, field=field, old_value=_s(old), new_value=_s(new),
                         actor_id=actor.id, reason=reason))


def _s(value) -> str | None:  # noqa: ANN001
    if value is None:
        return None
    return str(value)


def block(db: OrmSession, *, task: Task, actor: User, reason: str, create_blocker: bool = True) -> None:
    transition(db, task=task, to_status=TaskStatus.blocked, actor=actor, reason=reason)
    task.blocked_reason = reason
    if create_blocker:
        db.add(
            Blocker(
                title=f"مانع وظیفه {task.code}: {task.title[:120]}",
                description=reason,
                task_id=task.id,
                project_id=task.project_id,
                type=BlockerType.other,
                started_at=utcnow().date(),
                owner_id=actor.id,
                status=BlockerStatus.open,
                created_by=actor.id,
            )
        )


def unblock(db: OrmSession, *, task: Task, actor: User, note: str | None = None) -> None:
    transition(db, task=task, to_status=TaskStatus.in_progress, actor=actor, reason=note or "رفع مانع")
    task.blocked_reason = None


def submit_for_review(db: OrmSession, *, task: Task, actor: User, delivery_note: str) -> None:
    if actor.id != task.assignee_id:
        # همکار هم مجاز است — بررسی می‌شود
        from sqlalchemy import select as _s2
        from app.models.task import TaskCollaborator

        if db.scalar(_s2(TaskCollaborator).where(TaskCollaborator.task_id == task.id, TaskCollaborator.user_id == actor.id)) is None:
            raise HTTPException(status_code=403, detail="فقط مسئول اصلی یا همکار می‌تواند خروجی را ارسال کند")
    if not delivery_note or len(delivery_note.strip()) < 5:
        raise HTTPException(status_code=422, detail="ثبت خروجی و شواهد لازم برای ارسال به بررسی الزامی است")
    transition(db, task=task, to_status=TaskStatus.ready_for_review, actor=actor)
    task.delivery_note = delivery_note.strip()
    task.submitted_at = utcnow()
    if task.progress < 100:
        task.progress = 100


def approve(db: OrmSession, *, task: Task, actor: User, comment: str | None = None) -> None:
    if task.status != TaskStatus.ready_for_review:
        raise HTTPException(status_code=422, detail="وظیفه در وضعیت آماده بررسی نیست")
    task.status = TaskStatus.completed  # ثبت تاریخچه توسط فراخوان انجام می‌شود
    task.completed_at = utcnow()
    db.add(TaskStatusHistory(task_id=task.id, from_status=TaskStatus.ready_for_review.value,
                             to_status=TaskStatus.completed.value, actor_id=actor.id, reason=comment))
    task.progress = 100


def request_correction(db: OrmSession, *, task: Task, actor: User, reason: str) -> None:
    if task.status != TaskStatus.ready_for_review:
        raise HTTPException(status_code=422, detail="وظیفه در وضعیت آماده بررسی نیست")
    task.status = TaskStatus.needs_correction
    db.add(TaskStatusHistory(task_id=task.id, from_status=TaskStatus.ready_for_review.value,
                             to_status=TaskStatus.needs_correction.value, actor_id=actor.id, reason=reason))
