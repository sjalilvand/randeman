"""گزارش هفتگی: پیش‌نویس، ارسال، بررسی، تأیید و اصلاح (سند ۵.۵ و ۱۱.۲)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user
from app.core.db import get_db
from app.core.permissions import can_review_report, can_view_report, report_visibility_filter
from app.models.enums import ReportStatus
from app.models.report import ReviewAction, WeeklyReport, WeeklyReportItem, WeeklyReportVersion
from app.models.user import User
from app.services import notify, report_service
from app.services.audit_svc import audit

router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


class ReportIn(BaseModel):
    week_start: date
    summary: str | None = None
    blockers: str | None = None
    next_plan: str | None = None
    decision_requests: str | None = None
    items: list[dict] = []


def _payload(db: OrmSession, r: WeeklyReport, with_items: bool = True) -> dict:
    owner = db.get(User, r.user_id)
    approver = db.get(User, r.approver_id) if r.approver_id else None
    data = {
        "id": str(r.id), "user_id": str(r.user_id), "user_name": owner.full_name if owner else "—",
        "unit_id": str(r.unit_id) if r.unit_id else None,
        "week_start": r.week_start.isoformat(), "week_end": r.week_end.isoformat(),
        "status": r.status.value, "version": int(r.version),
        "summary": r.summary, "blockers": r.blockers, "next_plan": r.next_plan,
        "decision_requests": r.decision_requests,
        "approver_id": str(r.approver_id) if r.approver_id else None,
        "approver_name": approver.full_name if approver else None,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        "submitted_late": r.submitted_late,
    }
    if with_items:
        items = db.execute(select(WeeklyReportItem).where(WeeklyReportItem.report_id == r.id).order_by(WeeklyReportItem.id)).scalars().all()
        data["items"] = [
            {"id": str(i.id), "title": i.title, "description": i.description,
             "hours": float(i.hours) if i.hours else None, "kind": i.kind,
             "task_id": str(i.task_id) if i.task_id else None}
            for i in items
        ]
        versions = db.execute(select(WeeklyReportVersion).where(WeeklyReportVersion.report_id == r.id).order_by(WeeklyReportVersion.version.desc())).scalars().all()
        data["versions"] = [{"version": int(v.version), "created_at": v.created_at.isoformat(), "note": v.note} for v in versions]
        actions = db.execute(select(ReviewAction).where(ReviewAction.report_id == r.id).order_by(ReviewAction.created_at.desc())).scalars().all()
        data["review_actions"] = [
            {"action": a.action.value, "comment": a.comment, "at": a.created_at.isoformat(),
             "actor": (db.get(User, a.actor_id).full_name if db.get(User, a.actor_id) else "—")}
            for a in actions
        ]
    return data


@router.get("/my")
def my_report(week_start: date, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict | None:
    ws = report_service.week_start_for(week_start)
    r = db.scalar(select(WeeklyReport).where(WeeklyReport.user_id == actor.id, WeeklyReport.week_start == ws))
    return _payload(db, r) if r else None


@router.post("/my/generate", status_code=201)
def generate_my_report(
    body: dict, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    ws = report_service.week_start_for(date.fromisoformat(body.get("week_start") or date.today().isoformat()))
    r = report_service.get_or_create_draft(db, user=actor, week_start=ws)
    count = report_service.generate_draft_items(db, user=actor, report=r)
    return {**_payload(db, r), "generated_items": count}


@router.put("/my")
def update_my_report(
    body: ReportIn, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    ws = report_service.week_start_for(body.week_start)
    r = db.scalar(select(WeeklyReport).where(WeeklyReport.user_id == actor.id, WeeklyReport.week_start == ws))
    if r is None:
        r = report_service.get_or_create_draft(db, user=actor, week_start=ws)
    if r.status not in (ReportStatus.draft, ReportStatus.needs_correction):
        raise HTTPException(422, "گزارش ارسال‌شده/تأییدشده قابل ویرایش مستقیم نیست (سند AC-05)")
    r.summary, r.blockers, r.next_plan, r.decision_requests = (
        body.summary, body.blockers, body.next_plan, body.decision_requests
    )
    report_service.replace_items(db, report=r, items=body.items)
    return _payload(db, r)


@router.post("/my/submit")
def submit_my_report(
    body: dict, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    ws = report_service.week_start_for(date.fromisoformat(body.get("week_start") or date.today().isoformat()))
    r = db.scalar(select(WeeklyReport).where(WeeklyReport.user_id == actor.id, WeeklyReport.week_start == ws))
    if r is None:
        raise HTTPException(404, "برای این هفته گزارشی ساخته نشده است")
    late = report_service.submit(db, report=r, actor=actor)
    if r.approver_id:
        notify.notify(db, user_id=r.approver_id, type="report.submitted",
                      title=f"گزارش هفتگی {owner_name(db, r)} برای بررسی",
                      entity_type="weekly_report", entity_id=r.id)
    audit(db, actor_id=actor.id, action="weekly_report_submitted", entity_type="weekly_report", entity_id=r.id,
          summary=f"ارسال گزارش هفته {r.week_start.isoformat()} (تأخیر: {late})",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return {**_payload(db, r), "submitted_late": late}


def owner_name(db: OrmSession, r: WeeklyReport) -> str:
    u = db.get(User, r.user_id)
    return u.full_name if u else "—"


@router.get("/inbox")
def review_inbox(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> list[dict]:
    flt = report_visibility_filter(db, actor)
    conds = [WeeklyReport.status.in_([ReportStatus.submitted, ReportStatus.in_review])]
    if flt is not None:
        conds.append(or_(*flt))
    rows = db.execute(select(WeeklyReport).where(*conds).order_by(WeeklyReport.submitted_at.asc()).limit(200)).scalars().all()
    return [_payload(db, r) for r in rows]


@router.get("")
def browse_reports(
    user_id: uuid.UUID | None = None, week_start: date | None = None, status_filter: str | None = None,
    page: int = 1, size: int = 20,
    actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db),
) -> dict:
    flt = report_visibility_filter(db, actor)
    conds = list(flt) if flt is not None else []
    if user_id:
        conds.append(WeeklyReport.user_id == user_id)
    if week_start:
        conds.append(WeeklyReport.week_start == report_service.week_start_for(week_start))
    if status_filter:
        conds.append(WeeklyReport.status == status_filter)
    total = db.scalar(select(func.count()).select_from(WeeklyReport).where(*conds)) or 0
    rows = db.execute(select(WeeklyReport).where(*conds).order_by(WeeklyReport.week_start.desc())
                      .offset((page - 1) * size).limit(size)).scalars().all()
    return {"items": [_payload(db, r, with_items=False) for r in rows], "total": int(total), "page": page, "size": size}


def _get_report_or_404(db: OrmSession, report_id: uuid.UUID, actor: User) -> WeeklyReport:
    r = db.get(WeeklyReport, report_id)
    if r is None or not can_view_report(db, actor, r):
        raise HTTPException(404, "گزارش یافت نشد")
    return r


@router.get("/{report_id}")
def get_report(report_id: uuid.UUID, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    return _payload(db, _get_report_or_404(db, report_id, actor))


@router.get("/{report_id}/versions/{version}")
def get_version_snapshot(report_id: uuid.UUID, version: int, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    r = _get_report_or_404(db, report_id, actor)
    v = db.scalar(select(WeeklyReportVersion).where(WeeklyReportVersion.report_id == r.id, WeeklyReportVersion.version == version))
    if v is None:
        raise HTTPException(404, "نسخه یافت نشد")
    return v.snapshot


@router.post("/{report_id}/approve")
def approve_report(report_id: uuid.UUID, body: dict, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    r = _get_report_or_404(db, report_id, actor)
    if not can_review_report(db, actor, r):
        raise HTTPException(403, "فقط بررسی‌کننده مجاز می‌تواند تأیید کند (AC-22)")
    report_service.approve(db, report=r, actor=actor, comment=body.get("comment"))
    notify.notify(db, user_id=r.user_id, type="report.approved", title="گزارش هفتگی شما تأیید شد",
                  entity_type="weekly_report", entity_id=r.id)
    audit(db, actor_id=actor.id, action="weekly_report_approved", entity_type="weekly_report", entity_id=r.id,
          summary=f"تأیید گزارش هفته {r.week_start.isoformat()}",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, r)


@router.post("/{report_id}/request-correction")
def request_report_correction(report_id: uuid.UUID, body: dict, request: Request, actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    r = _get_report_or_404(db, report_id, actor)
    if not can_review_report(db, actor, r):
        raise HTTPException(403, "مجوز ندارید")
    comment = (body.get("comment") or "").strip()
    if not comment:
        raise HTTPException(422, "ثبت دلیل اصلاح الزامی است")
    report_service.request_correction(db, report=r, actor=actor, comment=comment)
    notify.notify(db, user_id=r.user_id, type="report.correction_requested",
                  title="گزارش هفتگی شما برای اصلاح بازگشت", body=comment,
                  entity_type="weekly_report", entity_id=r.id)
    audit(db, actor_id=actor.id, action="weekly_report_correction_requested", entity_type="weekly_report", entity_id=r.id,
          summary="درخواست اصلاح گزارش", ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    db.flush()
    return _payload(db, r)
