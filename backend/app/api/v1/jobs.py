"""کارهای پس‌زمینه و سلامت (سند ۹.۴ و ۱۷)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.db import get_db
from app.models.calendar import SystemSetting
from app.models.enums import JobStatus
from app.models.ops import BackgroundJob
from app.models.user import User
from pathlib import Path

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    job = db.get(BackgroundJob, job_id)
    if job is None:
        raise HTTPException(404, "کار یافت نشد")
    return {"id": str(job.id), "type": job.type, "status": job.status.value, "attempts": job.attempts,
            "last_error": job.last_error, "created_at": job.created_at.isoformat(),
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "result_path": job.result_path}


@router.get("/{job_id}/result")
def job_result(job_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    job = db.get(BackgroundJob, job_id)
    if job is None or job.type != "export_tasks_excel":
        raise HTTPException(404, "کار یافت نشد")
    if job.status != JobStatus.done or not job.result_path:
        raise HTTPException(422, "خروجی هنوز آماده نیست")
    path = Path(job.result_path)
    if not path.exists():
        raise HTTPException(404, "فایل خروجی یافت نشد یا منقضی شده است")
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/health/worker")
def worker_health(actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db)) -> dict:
    row = _get_setting(db, "worker_heartbeat")
    queue = int(db.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == JobStatus.pending)) or 0)
    running = int(db.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == JobStatus.running)) or 0)
    return {"heartbeat_at": row.value if row else None, "pending_jobs": queue, "running_jobs": running}


def _get_setting(db: OrmSession, key: str):  # noqa: ANN001
    return db.get(SystemSetting, key)
