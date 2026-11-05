-- ساخت پایگاه و حساب‌های مستقل راندمان (سند ۱۰.۱)
-- اجرا با حساب مدیر PostgreSQL — مقادیر رمز از طریق پارامتر psql ارسال شود:
--   psql -v app_pw="'...'" -v migrator_pw="'...'" -v report_pw="'...'" -v backup_pw="'...'" -f 01-create-database.sql
-- نام‌ها پیشنهادی‌اند و باید با سیاست نام‌گذاری سازمان تطبیق یابد.

\if :{?app_pw}
\else
\echo «رمزها را با پارامتر -v ارسال کنید»
\quit
\endif

-- حساب‌ها (بدون SUPERUSER)
CREATE ROLE randeman_app       LOGIN PASSWORD :app_pw      NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE randeman_migrator  LOGIN PASSWORD :migrator_pw NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE randeman_report    LOGIN PASSWORD :report_pw   NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE randeman_backup    LOGIN PASSWORD :backup_pw   NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT pg_read_all_data TO randeman_backup;  -- فقط خواندن برای pg_dump

-- پایگاه مستقل
CREATE DATABASE randeman OWNER randeman_migrator ENCODING 'UTF8';

-- همیشه به سامانه‌های دیگر دسترسی ندهید؛ این اسکریپت فقط پایگاه randeman را تنظیم می‌کند.
\connect randeman

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO randeman_migrator;

-- مجوزهای app پس از هر Migration (این بخش در پایان Migration نیز اجرا شود):
-- GRANT USAGE ON SCHEMA public TO randeman_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO randeman_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO randeman_app;
-- ALTER DEFAULT PRIVILEGES FOR ROLE randeman_migrator IN SCHEMA public
--     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO randeman_app;

-- حساب گزارش‌گیری: فقط روی Viewهای مجاز (در نسخه بعد ایجاد می‌شود)
-- GRANT USAGE ON SCHEMA public TO randeman_report;
-- GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO randeman_report;

-- pg_hba.conf: اتصال فقط از 127.0.0.1 با scram-sha-256؛ پورت 5432 نباید از اینترنت باز باشد.
