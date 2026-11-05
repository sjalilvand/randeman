-- مجوزهای DML برای randeman_app — پس از هر Migration اجرا شود (سند ۱۰.۱ و ۱۵.۴)
-- اجرا با حساب مدیر PostgreSQL:
--   psql -h 127.0.0.1 -U postgres -d randeman -f 02-post-migration-grants.sql

\connect randeman

GRANT USAGE ON SCHEMA public TO randeman_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO randeman_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO randeman_app;

ALTER DEFAULT PRIVILEGES FOR ROLE randeman_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO randeman_app;
ALTER DEFAULT PRIVILEGES FOR ROLE randeman_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO randeman_app;

-- حساب گزارش‌گیری (فقط خواندن) — برای خروجی‌های مدیریتی
GRANT USAGE ON SCHEMA public TO randeman_report;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO randeman_report;
ALTER DEFAULT PRIVILEGES FOR ROLE randeman_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO randeman_report;
