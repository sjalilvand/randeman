"""تنظیمات سامانه و تعریف شاخص‌ها (سند ۱۰.۲ و ۲۵)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.api.v1.deps import get_actor_ip, get_current_user, require_roles
from app.core.config import settings
from app.core.db import get_db
from app.models.calendar import MetricDefinition, SystemSetting
from app.models.user import User
from app.services.audit_svc import audit

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_SETTINGS: dict[str, dict] = {
    "report_deadline_weekday": {"value": settings.report_deadline_weekday, "description": "روز مهلت ارسال گزارش (0=دوشنبه ... 5=جمعه)"},
    "report_deadline_hour": {"value": settings.report_deadline_hour, "description": "ساعت مهلت ارسال گزارش"},
    "default_weekly_capacity_hours": {"value": settings.default_weekly_capacity_hours, "description": "ظرفیت هفتگی پیش‌فرض (ساعت)"},
    "week_starts_saturday": {"value": True, "description": "هفته از شنبه آغاز می‌شود"},
    "working_days": {"value": [5, 6, 0, 1, 2], "description": "روزهای کاری (weekday پایتون): شنبه تا چهارشنبه"},
    "max_upload_mb": {"value": settings.max_upload_mb, "description": "سقف حجم هر فایل مستند"},
    "brand_title": {"value": settings.app_name, "description": "عنوان نمایشی سامانه"},
}


def _get_setting(db: OrmSession, key: str):
    return db.get(SystemSetting, key)


@router.get("")
def get_settings(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> dict:
    out = {}
    for key, meta in DEFAULT_SETTINGS.items():
        row = _get_setting(db, key)
        out[key] = {
            "value": row.value if row else meta["value"],
            "description": meta["description"],
            "overridden": row is not None,
        }
    return out


class SettingIn(BaseModel):
    value: object


@router.put("/{key}")
def set_setting(key: str, body: SettingIn, request: Request, actor: User = Depends(require_roles()), db: OrmSession = Depends(get_db)) -> dict:
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(422, "کلید تنظیم شناخته‌شده نیست")
    row = _get_setting(db, key)
    if row is None:
        row = SystemSetting(key=key, value=body.value, description=DEFAULT_SETTINGS[key]["description"], updated_by=actor.id)
        db.add(row)
    else:
        row.value = body.value
        row.updated_by = actor.id
    audit(db, actor_id=actor.id, action="setting_changed", entity_type="setting", summary=f"تغییر {key} → {body.value}",
          ip=get_actor_ip(request), user_agent=request.headers.get("user-agent"))
    return {"key": key, "value": body.value}


@router.get("/metrics")
def metric_definitions(actor: User = Depends(get_current_user), db: OrmSession = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(MetricDefinition).where(MetricDefinition.is_active.is_(True))).scalars().all()
    return [{"key": m.key, "version": m.version, "title_fa": m.title_fa, "formula": m.formula,
             "description": m.description} for m in rows]
