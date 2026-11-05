"""Seed داده اولیه: نقش‌ها، حساب‌ها، ساختار نمونه و تعریف شاخص‌ها (سند ۱۹ فاز ۰)."""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.calendar import MetricDefinition, SystemSetting
from app.models.enums import Priority, ProjectStatus, TaskStatus
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskStatusHistory
from app.models.user import OrganizationUnit, Role, User, UserRole

ROLES = [
    ("senior_manager", "مدیر ارشد", "مشاهده سازمانی و تصمیم‌گیری"),
    ("unit_manager", "مدیر واحد", "مدیریت وظایف و گزارش‌های واحد"),
    ("project_manager", "مدیر پروژه", "مدیریت پروژه‌های مجاز"),
    ("employee", "کارمند / کارشناس", "انجام کار و ثبت فعالیت و مستند"),
    ("pmo", "مسئول تعالی / PMO", "پایش پروژه‌ها و هماهنگی گزارش‌ها"),
    ("observer", "ناظر", "مشاهده اطلاعات مجاز"),
    ("auditor", "ممیز", "بررسی سوابق و شواهد در محدوده تعیین‌شده"),
    ("sys_admin", "مدیر سامانه", "مدیریت فنی حساب‌ها و تنظیمات — تأییدکننده پیش‌فرض عملکرد نیست"),
]

METRICS = [
    ("project_progress_reported", "پیشرفت گزارش‌شده پروژه",
     "مجموع (وزن وظیفه × درصد پیشرفت) ÷ مجموع وزن وظایف معتبر", "سند ۷.۱ — حذف وظایف لغوشده؛ ثبت تاریخچه تغییر وزن"),
    ("project_progress_approved", "پیشرفت تأییدشده پروژه",
     "مجموع وزن وظایف تکمیل و تأییدشده ÷ مجموع وزن وظایف معتبر × ۱۰۰", "سند ۷.۱ — پذیرش بخشی از خروجی با اقلام قابل تحویل مستقل"),
    ("overdue_pct", "درصد تعهدات معوق در پایان دوره",
     "وظایف مبنا که تا پایان دوره تأیید نشده‌اند ÷ تعداد وظایف مبنا × ۱۰۰", "سند ۷.۲ — مخرج صفر: غیرقابل محاسبه"),
    ("on_time_pct", "درصد تکمیل به‌موقع",
     "وظایف تأییدشده تا سررسید ÷ وظایف معتبر سررسیدشده × ۱۰۰", "سند ۷.۳ — دو مبنا: سررسید مبنا و سررسید جاری مصوب"),
    ("delay_breakdown", "تفکیک مدت تأخیر",
     "تأخیر تا ارسال / زمان انتظار بررسی / تأخیر تا تأیید نهایی", "سند ۷.۴ — روز تقویمی؛ در عنوان گزارش مشخص می‌شود"),
    ("workload_ratio", "بار برنامه‌ریزی‌شده به ظرفیت",
     "ساعات تخمینی تخصیص‌یافته در دوره ÷ ظرفیت قابل استفاده × ۱۰۰", "سند ۷.۵ — پوشش داده نیز نمایش داده می‌شود"),
]


def seed(with_demo: bool) -> None:
    db = SessionLocal()
    try:
        # نقش‌ها
        for code, name, desc in ROLES:
            if db.scalar(select(Role).where(Role.code == code)) is None:
                db.add(Role(code=code, name_fa=name, description=desc))
        db.flush()

        # تعریف شاخص‌ها
        for key, title, formula, desc in METRICS:
            if db.scalar(select(MetricDefinition).where(MetricDefinition.key == key)) is None:
                db.add(MetricDefinition(key=key, title_fa=title, formula=formula, description=desc))

        # تنظیمات پیش‌فرض
        for key, value in {
            "report_deadline_weekday": settings.report_deadline_weekday,
            "report_deadline_hour": settings.report_deadline_hour,
            "default_weekly_capacity_hours": settings.default_weekly_capacity_hours,
            "brand_title": settings.app_name,
        }.items():
            if db.get(SystemSetting, key) is None:
                db.add(SystemSetting(key=key, value=value))

        # مدیر سامانه
        admin = db.scalar(select(User).where(User.username == "admin"))
        if admin is None:
            admin = User(
                username="admin",
                password_hash=hash_password("Randeman@1404"),
                first_name="مدیر", last_name="سامانه",
                position="مدیر سامانه",
            )
            db.add(admin)
            db.flush()
            admin_role = db.scalar(select(Role).where(Role.code == "sys_admin"))
            db.add(UserRole(user_id=admin.id, role_id=admin_role.id))

        if with_demo:
            _seed_demo(db)
        db.commit()
        print("✅ Seed انجام شد.")
        print("   حساب مدیر سامانه: admin / Randeman@1404  (فقط برای آزمایش؛ در عملیات رمز را عوض کنید)")
    finally:
        db.close()


def _seed_demo(db) -> None:  # noqa: ANN001
    role = {c: db.scalar(select(Role).where(Role.code == c)) for c, _, _ in ROLES}

    def make_user(username: str, first: str, last: str, code: str, position: str, unit: OrganizationUnit | None,
                  manager: User | None) -> User:
        u = db.scalar(select(User).where(User.username == username))
        if u is not None:
            return u
        u = User(username=username, password_hash=hash_password("Randeman@1404"), first_name=first, last_name=last,
                 position=position, primary_unit_id=unit.id if unit else None,
                 direct_manager_id=manager.id if manager else None)
        db.add(u)
        db.flush()
        if role.get(code):
            db.add(UserRole(user_id=u.id, role_id=role[code].id))
        return u

    it = db.scalar(select(OrganizationUnit).where(OrganizationUnit.name == "فناوری اطلاعات"))
    if it is None:
        root = OrganizationUnit(name="مدیریت", code="MNG")
        db.add(root)
        db.flush()
        ceo = make_user("ceo", "سارا", "محمدی", "senior_manager", "مدیر ارشد", root, None)
        root.manager_id = ceo.id
        it = OrganizationUnit(name="فناوری اطلاعات", code="IT", parent_id=root.id)
        hr = OrganizationUnit(name="منابع انسانی", code="HR", parent_id=root.id)
        fin = OrganizationUnit(name="مالی و اداری", code="FIN", parent_id=root.id)
        db.add_all([it, hr, fin])
        db.flush()
        m_it = make_user("m.it", "رضا", "کریمی", "unit_manager", "مدیر واحد فناوری اطلاعات", it, ceo)
        it.manager_id = m_it.id
        m_hr = make_user("m.hr", "مریم", "احمدی", "unit_manager", "مدیر واحد منابع انسانی", hr, ceo)
        hr.manager_id = m_hr.id
        emp1 = make_user("emp1", "علی", "رحیمی", "employee", "کارشناس نرم‌افزار", it, m_it)
        emp2 = make_user("emp2", "نگار", "سلطانی", "employee", "کارشناس شبکه", it, m_it)
        emp3 = make_user("emp3", "حسین", "قاسمی", "employee", "کارشناس جذب", hr, m_hr)
        pmo = make_user("pmo", "زهرا", "نوری", "pmo", "مسئول تعالی", root, ceo)
        pm = make_user("pm", "امیر", "شریفی", "project_manager", "مدیر پروژه", it, m_it)
        make_user("observer", "لیلا", "کاظمی", "observer", "ناظر", root, ceo)
        make_user("auditor", "فرهاد", "موسوی", "auditor", "ممیز", root, ceo)
        db.flush()

        titles = [
            "پورتال خدمات الکترونیک داخلی", "استقرار سامانه مدیریت پروژه", "به‌روزرسانی زیرساخت شبکه",
            "سامانه آموزش کارکنان", "مستندسازی فرایندهای سازمانی", "داشبورد شاخص‌های کلیدی",
        ]
        statuses = [ProjectStatus.active, ProjectStatus.active, ProjectStatus.active,
                    ProjectStatus.draft, ProjectStatus.paused, ProjectStatus.completed]
        for i, (title, st) in enumerate(zip(titles, statuses), start=1):
            p = db.scalar(select(Project).where(Project.title == title))
            if p is not None:
                continue
            p = Project(code=f"PRJ-DEMO{i:02d}", title=title, description=f"پروژه نمونه {i} برای آزمون سامانه",
                        goal="هدف نمونه — با اطلاعات واقعی جایگزین شود", category="نمونه",
                        manager_id=pm.id if i % 2 else m_it.id, lead_unit_id=it.id, status=st,
                        priority=Priority.medium, start_date=None, end_date=None)
            db.add(p)
            db.flush()
            db.add(ProjectMember(project_id=p.id, user_id=p.manager_id, role_in_project="manager"))
            db.add(ProjectMember(project_id=p.id, user_id=emp1.id, role_in_project="member"))
            tasks = [
                ("تحلیل نیازمندی‌ها", TaskStatus.completed, 100),
                ("طراحی رابط کاربری", TaskStatus.in_progress, 55),
                ("پیاده‌سازی نسخه اولیه", TaskStatus.assigned, 0),
                ("آزمون پذیرش", TaskStatus.draft, 0),
            ]
            for j, (t_title, t_status, prog) in enumerate(tasks, start=1):
                t = Task(code=f"T-DEMO{i}{j}", title=f"{title} — {t_title}", project_id=p.id,
                         unit_id=it.id, assignee_id=emp1.id if j % 2 else emp2.id, created_by=pm.id,
                         base_due_date=None, current_due_date=None, status=t_status, progress=prog,
                         weight=1.0, priority=Priority.medium)
                db.add(t)
                db.flush()
                db.add(TaskStatusHistory(task_id=t.id, from_status=None, to_status=t_status.value,
                                         actor_id=pm.id, reason="داده نمونه"))
        print("   داده نمونه: واحدها، کاربران (رمز: Randeman@1404) و ۶ پروژه ایجاد شد.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed سامانه راندمان")
    parser.add_argument("--with-demo", action="store_true", help="ایجاد داده نمونه (واحدها، کاربران، ۶ پروژه)")
    args = parser.parse_args()
    try:
        seed(with_demo=args.with_demo)
    except Exception as exc:  # noqa: BLE001
        print(f"خطا در seed: {exc}", file=sys.stderr)
        raise
