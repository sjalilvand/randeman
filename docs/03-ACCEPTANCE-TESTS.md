# نگاشت سناریوهای پذیرش (سند ۱۸.۲) به پیاده‌سازی

| کد | سناریو | محل کنترل | وضعیت |
|---|---|---|---|
| AC-01 | درخواست مستقیم رکورد غیرمجاز | `permissions.py` + پاسخ 404 | ✅ آزمون `test_direct_access_to_forbidden_record` |
| AC-02 | تأیید وظیفه فقط توسط شخص مجاز | `can_review_task` + مسیر approve | ✅ آزمون `test_full_workflow` |
| AC-03 | تغییر سررسید: ثبت قبلی/جدید/دلیل/تأیید | `TaskChangeRequest` + `TaskChangeLog`، حفظ سررسید مبنا | ✅ آزمون `test_due_change_request_flow` |
| AC-04 | بازگشایی با ثبت عامل و دلیل | `task_service.reopen` + ممیزی | ✅ آزمون `test_full_workflow` |
| AC-05 | ویرایش گزارش تأییدشده مسدود | `PUT /weekly-reports/my` برای وضعیت قفل | ✅ آزمون `test_report_flow_and_self_approval_ban` |
| AC-06 | انتقال کاربر بین واحدها — حفظ تاریخچه | `UserUnitAssignment` (تاریخچه) + انتساب گزارش به واحد زمان ثبت | ✅ مدل |
| AC-07 | دانلود فایل محدود — کنترل مستقل مجوز | مسیر download با کنترل ACL | ✅ `test_documents.py` |
| AC-08 | فایل اجرایی/اسکریپت رد شود | whitelist پسوند + امضای محتوا | ✅ آزمون `test_executable_extension_rejected` |
| AC-09 | ویرایش هم‌زمان — تعارض کنترل‌شده | `version` روی Task/Project/Blocker (سند ۱۰.۴) | ✅ مدل |
| AC-10 | مخرج صفر شاخص — غیرقابل محاسبه | بازگشت None + نمایش «قابل محاسبه نیست» | ✅ آزمون `test_overdue_pct_zero_divisor` |
| AC-11 | ارسال به‌موقع و تأیید دیرهنگام — تفکیک | `submitted_at`، `submitted_late`، `delay_stats` (سه مؤلفه) | ✅ آزمون + شاخص |
| AC-12 | متن شبیه فرمول در Excel | `safe_cell` با پیشوند ' | ✅ آزمون `test_formula_injection_guard` |
| AC-13 | توقف API — استمرار Worker | فرایندهای مستقل؛ Worker مستقل از API | 🔲 تست نصب |
| AC-14 | بازیابی در محیط پاک | راهنمای بازیابی | 🔲 تست نصب |
| AC-15 | کلیک عدد داشبورد → جزئیات سازگار | فیلترهای داشبورد = فیلترهای فهرست | ✅ رابط |
| AC-16 | توقف ClamAV → ماندن فایل در قرنطینه | `finalize_scan` — عدم دسترسی ⇒ quarantined + دانلود 423 | ✅ آزمون `test_upload_without_clamav_stays_quarantined` |
| AC-17 | اجرای مجدد کار پس‌زمینه — بدون اثر تکراری | صف + idempotency_key + اجاره (Lease) | ✅ مدل |
| AC-18 | انتشار نسخه جدید بدون اختلال | releases نسخه‌دار + migration جدا + راهنما | 🔲 تست نصب |
| AC-19 | قطع Worker وسط کار → بازیابی پس از Lease | `lease_until` + backoff + max_attempts | ✅ مدل |
| AC-20 | گزارش تاریخی مستقل از تغییرات بعدی | `WeeklyReportVersion.snapshot` تغییرناپذیر | ✅ آزمون `test_report_history_snapshot_immutable` |
| AC-21 | ساخت React — بدون Vite Dev Server در تولید | `npm run build` + ارائه dist توسط Nginx | ✅ CI |
| AC-22 | تأیید گزارش خود → رد | `can_review_report` (صاحب گزارش ⇒ False) | ✅ آزمون |
