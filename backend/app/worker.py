"""Worker مستقل — صف پایدار، اعلان، اسکن مستندات و یادآوری (سند ۹.۴ و ۱۵.۴).

- زمان‌بند فقط در Worker فعال است؛ نه در پردازش API
- برداشت کار با اجاره (Lease) و حداقل یک‌بار؛ عملیات idempotent
"""
from __future__ import annotations

import logging
import socket
import time
import uuid
from datetime import timedelta

from sqlalchemy import select, update

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models.base import utcnow
from app.models.calendar import SystemSetting
from app.models.enums import JobStatus
from app.models.ops import BackgroundJob, OutboxEvent

logger = logging.getLogger("randeman.worker")

WORKER_ID = f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


def heartbeat(db) -> None:  # noqa: ANN001
    row = db.get(SystemSetting, "worker_heartbeat")
    if row is None:
        db.add(SystemSetting(key="worker_heartbeat", value=utcnow().isoformat()))
    else:
        row.value = utcnow().isoformat()


def claim_job(db) -> BackgroundJob | None:  # noqa: ANN001
    now = utcnow()
    if engine.dialect.name == "postgresql":
        from sqlalchemy.orm import load_opt  # noqa: F401

        with db.begin_nested():
            job = db.execute(
                select(BackgroundJob)
                .where(BackgroundJob.status == JobStatus.pending,
                       (BackgroundJob.run_at.is_(None)) | (BackgroundJob.run_at <= now))
                .order_by(BackgroundJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).scalars().first()
            if job is None:
                return None
            job.status = JobStatus.running
            job.leased_by = WORKER_ID
            job.lease_until = now + timedelta(seconds=settings.worker_lease_seconds)
            job.attempts = (job.attempts or 0) + 1
        return job
    # SQLite و سایر موتورها: برداشت با شرط وضعیت
    job = db.execute(
        select(BackgroundJob)
        .where(BackgroundJob.status == JobStatus.pending,
               (BackgroundJob.run_at.is_(None)) | (BackgroundJob.run_at <= now))
        .order_by(BackgroundJob.created_at).limit(1)
    ).scalars().first()
    if job is None:
        return None
    result = db.execute(
        update(BackgroundJob)
        .where(BackgroundJob.id == job.id, BackgroundJob.status == JobStatus.pending)
        .values(status=JobStatus.running, leased_by=WORKER_ID,
                lease_until=now + timedelta(seconds=settings.worker_lease_seconds),
                attempts=(job.attempts or 0) + 1)
    )
    if result.rowcount != 1:  # نوع رقابتی — کاربر دیگری برداشت کرد
        return None
    db.refresh(job)
    return job


def requeue_or_fail(db, job: BackgroundJob, error: str) -> None:  # noqa: ANN001
    if (job.attempts or 0) >= (job.max_attempts or 3):
        job.status = JobStatus.failed
        job.last_error = error[:2000]
        job.finished_at = utcnow()
    else:
        job.status = JobStatus.pending
        job.last_error = error[:2000]
        job.run_at = utcnow() + timedelta(seconds=30 * (2 ** (job.attempts or 1)))  # backoff
    db.commit()


def handle_job(db, job: BackgroundJob) -> None:  # noqa: ANN001
    payload = job.payload or {}
    if job.type == "scan_document":
        from app.services.document_service import finalize_scan

        result = finalize_scan(db, document_id=uuid.UUID(payload["document_id"]))
        logger.info("اسکن مستند %s → %s", payload["document_id"], result)
    elif job.type == "export_tasks_excel":
        _export_tasks_excel(db, job)
    else:
        raise ValueError(f"نوع کار ناشناخته: {job.type}")
    if job.status != JobStatus.done:
        job.status = JobStatus.done
        job.finished_at = utcnow()
    db.commit()


def _export_tasks_excel(db, job: BackgroundJob) -> None:  # noqa: ANN001
    from pathlib import Path

    from app.core.config import settings as s
    from app.models.task import Task
    from app.models.user import User
    from app.services import excel

    rows = db.execute(select(Task).order_by(Task.created_at.desc()).limit(50000)).scalars().all()
    cols = ["کد", "عنوان", "مسئول", "وضعیت", "اولویت", "پیشرفت", "سررسید جاری", "سررسید مبنا"]
    data = []
    for t in rows:
        assignee = db.get(User, t.assignee_id)
        data.append([t.code, t.title, assignee.full_name if assignee else "—", t.status.value,
                     t.priority.value, f"{t.progress}%", excel.jdate_str(t.current_due_date),
                     excel.jdate_str(t.base_due_date)])
    out_dir = Path(s.exports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tasks-{job.id}.xlsx"
    buf = excel.build_workbook(title="گزارش وظایف", period_label=None, filters_label=str(job.payload or {}),
                               columns=cols, rows=data, generated_by="Worker")
    out_path.write_bytes(buf.getvalue())
    job.result_path = str(out_path)


def process_outbox(db) -> int:  # noqa: ANN001
    events = db.execute(select(OutboxEvent).where(OutboxEvent.status == "pending").limit(50)).scalars().all()
    for ev in events:
        # کانال ایمیل وابسته به SMTP است؛ در MVP فقط پردازش‌شده علامت می‌خورد
        ev.status = "processed"
        ev.processed_at = utcnow()
        ev.attempts = (ev.attempts or 0) + 1
    if events:
        db.commit()
    return len(events)


def send_reminders(db) -> int:  # noqa: ANN001
    """یادآوری سررسید نزدیک/معوق — یک‌بار در روز برای هر وظیفه (سند ۵.۷)."""
    from datetime import date

    from fastapi import HTTPException  # noqa: F401
    from sqlalchemy import or_

    from app.models.enums import TaskStatus
    from app.models.task import Task
    from app.models.ops import Notification
    from app.services import notify as _notify
    from app.services.report_service import TZ

    today = utcnow().astimezone(TZ).date()
    soon = today + timedelta(days=2)
    non_final = [s for s in TaskStatus if s.value not in ("completed", "cancelled")]
    tasks = db.execute(
        select(Task).where(
            Task.status.in_(non_final),
            or_(Task.current_due_date <= soon, Task.current_due_date < today),
        ).limit(500)
    ).scalars().all()
    sent = 0
    for t in tasks:
        key_day = f"{t.id}:{today.isoformat()}"
        exists = db.execute(
            select(Notification.id).where(Notification.user_id == t.assignee_id,
                                          Notification.type == "task.reminder",
                                          Notification.title.like(f"%{t.code}%"),
                                          Notification.created_at >= utcnow() - timedelta(hours=20)).limit(1)
        ).scalar()
        if exists is not None:
            continue
        overdue = bool(t.current_due_date and t.current_due_date < today)
        _notify.notify(
            db, user_id=t.assignee_id, type="task.reminder",
            title=f"{'⚠️ معوق: ' if overdue else 'یادآوری: '}{t.code} — {t.title[:80]}",
            body=("سررسید گذشته است" if overdue else f"سررسید نزدیک است: {t.current_due_date.isoformat()}"),
            entity_type="task", entity_id=t.id,
        )
        sent += 1
    if sent:
        db.commit()
    return sent


def run_loop() -> None:  # pragma: no cover — حلقه بی‌پایان عملیاتی
    logger.info("Worker راندمان آغاز شد: %s", WORKER_ID)
    last_reminder = 0.0
    while True:
        try:
            with SessionLocal() as db:
                heartbeat(db)
                db.commit()
                process_outbox(db)
                if time.time() - last_reminder > 3600:  # ساعتی یک‌بار
                    send_reminders(db)
                    last_reminder = time.time()
                job = claim_job(db)
                if job is not None:
                    logger.info("اجرای کار %s (%s)", job.id, job.type)
                    try:
                        handle_job(db, job)
                    except Exception as exc:  # noqa: BLE001
                        db.rollback()
                        logger.exception("خطای کار %s", job.id)
                        with SessionLocal() as db2:
                            fresh = db2.get(BackgroundJob, job.id)
                            if fresh is not None:
                                requeue_or_fail(db2, fresh, str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("خطای حلقه Worker")
        time.sleep(5)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        run_loop()
    except KeyboardInterrupt:
        logger.info("Worker متوقف شد")
