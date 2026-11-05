"""منطق دامنه گزارش هفتگی — هفته شنبه تا جمعه، نسخه‌بندی و گردش بررسی (سند ۵.۵)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core.config import settings
from app.models.base import utcnow
from app.models.enums import ReportStatus, ReviewActionType
from app.models.report import ReviewAction, WeeklyReport, WeeklyReportItem, WeeklyReportVersion
from app.models.user import User

TZ = ZoneInfo(settings.timezone_name)


def week_start_for(day: date) -> date:
    """شنبه آغاز هفته — weekday پایتون: شنبه=5."""
    offset = (day.weekday() - 5) % 7
    return day - timedelta(days=offset)


def week_range(week_start: date) -> tuple[date, date]:
    return week_start, week_start + timedelta(days=6)


def deadline_for_week(week_start: date) -> datetime:
    """مهلت ارسال: پایان‌های هفته ساعت تنظیم‌شده، به وقت تهران."""
    _, week_end = week_range(week_start)
    naive = datetime(week_end.year, week_end.month, week_end.day, settings.report_deadline_hour, 0)
    return naive.replace(tzinfo=TZ)


def get_or_create_draft(db: OrmSession, *, user: User, week_start: date) -> WeeklyReport:
    """یک گزارش اصلی برای هر فرد و بازه — یکتا در سطح پایگاه."""
    report = db.scalar(
        select(WeeklyReport).where(WeeklyReport.user_id == user.id, WeeklyReport.week_start == week_start)
    )
    if report is None:
        start, end = week_range(week_start)
        report = WeeklyReport(
            user_id=user.id, unit_id=user.primary_unit_id, week_start=start, week_end=end, status=ReportStatus.draft
        )
        db.add(report)
        db.flush()
    return report


def generate_draft_items(db: OrmSession, *, user: User, report: WeeklyReport) -> int:
    """تولید پیش‌نویس از فعالیت‌ها و وظایف باز — فقط وقتی گزارش خالی است."""
    start, end = week_range(report.week_start)
    existing = db.scalar(select(WeeklyReportItem.id).where(WeeklyReportItem.report_id == report.id).limit(1))
    if existing is not None:
        return 0

    from app.models.activity import Activity

    acts = db.execute(
        select(Activity).where(
            Activity.user_id == user.id, Activity.activity_date >= start, Activity.activity_date <= end
        ).order_by(Activity.activity_date)
    ).scalars().all()
    for a in acts:
        db.add(
            WeeklyReportItem(
                report_id=report.id, activity_id=a.id, task_id=a.task_id,
                title=a.title, description=a.description, kind="done",
                hours=(a.duration_minutes / 60) if a.duration_minutes else None,
            )
        )
    return len(acts)


def replace_items(db: OrmSession, *, report: WeeklyReport, items: list[dict]) -> None:
    db.execute(
        select(WeeklyReportItem.id).where(WeeklyReportItem.report_id == report.id)
    )  # لمس نشست
    from sqlalchemy import delete

    db.execute(delete(WeeklyReportItem).where(WeeklyReportItem.report_id == report.id))
    for it in items:
        db.add(
            WeeklyReportItem(
                report_id=report.id,
                task_id=_uuid(it.get("task_id")),
                activity_id=_uuid(it.get("activity_id")),
                title=(it.get("title") or "").strip()[:250],
                description=it.get("description"),
                hours=it.get("hours"),
                kind=it.get("kind") or "done",
            )
        )
    db.flush()


def _uuid(value) -> uuid.UUID | None:  # noqa: ANN001
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def snapshot(db: OrmSession, *, report: WeeklyReport, actor: User, note: str | None = None) -> None:
    """اسنپ‌شات تغییرناپذیر از وضعیت ارسال — تصویر تاریخی (سند ۵.۵)."""
    items = db.execute(select(WeeklyReportItem).where(WeeklyReportItem.report_id == report.id)).scalars().all()
    snap = {
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "user_id": str(report.user_id),
        "unit_id": str(report.unit_id) if report.unit_id else None,
        "summary": report.summary,
        "blockers": report.blockers,
        "next_plan": report.next_plan,
        "decision_requests": report.decision_requests,
        "items": [
            {"title": i.title, "description": i.description, "hours": float(i.hours) if i.hours else None,
             "kind": i.kind, "task_id": str(i.task_id) if i.task_id else None}
            for i in items
        ],
    }
    db.add(WeeklyReportVersion(report_id=report.id, version=report.version, snapshot=snap, created_by=actor.id, note=note))


def resolve_approver(db: OrmSession, *, user: User) -> User:
    """جانشین‌سازی: مدیر مستقیم، سپس مدیر واحد؛ تأییدکننده هرگز خود فرد نیست."""
    if user.direct_manager_id and user.direct_manager_id != user.id:
        mgr = db.get(User, user.direct_manager_id)
        if mgr and mgr.is_active:
            return mgr
    if user.primary_unit_id:
        from app.models.user import OrganizationUnit

        unit = db.get(OrganizationUnit, user.primary_unit_id)
        for candidate in (unit.manager_id if unit else None, unit.deputy_manager_id if unit else None):
            if candidate and candidate != user.id:
                approver = db.get(User, candidate)
                if approver and approver.is_active:
                    return approver
    raise HTTPException(status_code=422, detail="بررسی‌کننده‌ای برای شما تعیین نشده است؛ با مدیر سامانه هماهنگ کنید")


def submit(db: OrmSession, *, report: WeeklyReport, actor: User) -> bool:
    """ارسال گزارش — خروجی: ارسال با تأخیر بود یا نه."""
    if report.status not in (ReportStatus.draft, ReportStatus.needs_correction):
        raise HTTPException(status_code=422, detail="گزارش در وضعیت قابل ارسال نیست")
    items = db.execute(select(WeeklyReportItem).where(WeeklyReportItem.report_id == report.id)).scalars().all()
    if not items and not (report.summary or "").strip():
        raise HTTPException(status_code=422, detail="گزارش خالی قابل ارسال نیست")
    approver = resolve_approver(db, user=actor)
    if approver.id == actor.id:
        raise HTTPException(status_code=422, detail="تأییدکننده نمی‌تواند خود فرد باشد")

    report.version = int(report.version) + 1
    report.approver_id = approver.id
    report.submitted_at = utcnow()
    report.status = ReportStatus.submitted
    late = utcnow().astimezone(TZ) > deadline_for_week(report.week_start)
    report.submitted_late = late
    snapshot(db, report=report, actor=actor, note="ارسال")
    db.add(ReviewAction(report_id=report.id, actor_id=actor.id, action=ReviewActionType.comment,
                        comment="ارسال گزارش"))
    return late


def approve(db: OrmSession, *, report: WeeklyReport, actor: User, comment: str | None = None) -> None:
    if report.status not in (ReportStatus.submitted, ReportStatus.in_review):
        raise HTTPException(status_code=422, detail="گزارش در وضعیت قابل تأیید نیست")
    report.status = ReportStatus.approved
    report.approved_at = utcnow()
    snapshot(db, report=report, actor=actor, note="تأیید")
    db.add(ReviewAction(report_id=report.id, actor_id=actor.id, action=ReviewActionType.approve, comment=comment))


def request_correction(db: OrmSession, *, report: WeeklyReport, actor: User, comment: str) -> None:
    if report.status not in (ReportStatus.submitted, ReportStatus.in_review, ReportStatus.approved):
        raise HTTPException(status_code=422, detail="گزارش در وضعیت قابل بازگشت برای اصلاح نیست")
    report.status = ReportStatus.needs_correction
    db.add(ReviewAction(report_id=report.id, actor_id=actor.id,
                        action=ReviewActionType.request_correction, comment=comment))
