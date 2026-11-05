"""پیکربندی سامانه راندمان — از طریق متغیرهای محیطی یا فایل .env کنترل می‌شود."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="RANDEMAN_", extra="ignore"
    )

    # هویت
    app_name: str = "راندمان"
    app_subtitle: str = "سامانه مدیریت عملکرد، وظایف، پروژه‌ها و مستندات سازمانی"
    env: str = "dev"  # dev | test | prod

    # پایگاه داده — در عملیات: postgresql+psycopg://randeman_app:...@127.0.0.1:5432/randeman
    database_url: str = "sqlite:///./randeman.db"

    # نشست و کوکی
    session_cookie_name: str = "randeman_session"
    session_ttl_minutes: int = 480
    cookie_secure: bool = False          # در عملیات روی HTTPS باید True باشد
    cookie_samesite: str = "lax"
    login_max_failed: int = 5
    login_lock_minutes: int = 15

    # مستندات و فایل‌ها
    documents_dir: str = "./data/documents"
    quarantine_dir: str = "./data/quarantine"
    exports_dir: str = "./data/exports"
    max_upload_mb: int = 20
    allowed_extensions: str = "pdf,docx,xlsx,pptx,jpg,jpeg,png,txt"

    # ClamAV — در صورت خالی بودن، فایل در قرنطینه می‌ماند (مطابق سند ۵.۶)
    clamd_host: str = ""
    clamd_port: int = 3310
    clamd_timeout: int = 20

    # پردازش
    api_workers: int = 2
    db_pool_size: int = 5
    db_max_overflow: int = 2
    worker_lease_seconds: int = 600
    worker_heartbeat_seconds: int = 60

    # ارائه رابط ساخته‌شده از همان پورت API — حالت تک‌پورت (تصمیم ۲۵.۲ و پورت 8095)
    # مسیر پوشه dist رابط؛ خالی = غیرفعال (استقرار عملیاتی: Nginx 8087)
    serve_dist_dir: str = ""

    # تقویم و زمان (تصمیم ۲۵.۲: شروع هفته شنبه، مهلت گزارش پنجشنبه ۱۲:۰۰ تهران)
    timezone_name: str = "Asia/Tehran"
    default_weekly_capacity_hours: float = 40.0
    report_deadline_weekday: int = 3   # weekday پایتون: شنبه=5 ... پنجشنبه=3
    report_deadline_hour: int = 12
    report_approval_deadline_hour: int = 12  # مهلت بررسی مدیر واحد: شنبه ۱۲:۰۰

    # اعلان ایمیلی — فاز ۲ (تصمیم ۲۵.۲: SMTP داخلی سازمان؛ خالی = اعلان درون‌برنامه‌ای فقط)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # امنیت
    docs_enabled: bool = True           # در عملیات False تا OpenAPI عمومی نشود
    trusted_proxies: str = "127.0.0.1"  # فقط پراکسی‌های شناخته‌شده
    cors_origins: str = ""              # هم‌مبدأ پیش‌فرض؛ برای dev خالی (پروکسی Vite)

    def allowed_ext_list(self) -> list[str]:
        return sorted({e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()})


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
