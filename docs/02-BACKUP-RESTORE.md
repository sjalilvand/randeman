# پشتیبان‌گیری و بازیابی PostgreSQL و مستندات (سند ۱۶)

> کپی مستقیم پوشه داده PostgreSQL پشتیبان معتبر محسوب نمی‌شود.

## برنامه پایه

| مورد | برنامه |
|---|---|
| پشتیبان منطقی دیتابیس | روزانه `pg_dump` قالب Custom |
| بسته کامل هفتگی | دیتابیس + مستندات + تنظیمات |
| مستندات | روزانه و پس از تغییرات مهم |
| انتقال خارج از سرور | روزانه |
| گزارش صحت | هر نوبت (Manifest + Hash) |
| آزمون بازیابی نمونه | ماهانه |
| مانور کامل | هر سه ماه |
| تحویل مرکز | هر پنجشنبه |

اهداف: RPO دیتابیس و مستندات ≤ ۲۴ ساعت؛ RTO ≤ ۸ ساعت (مشروط به آزمون).

## اجرای روزانه

`deploy\windows\backup-daily.ps1` را با Task Scheduler (یا NSSM/Task) روی ساعت کم‌بار اجرا کنید:

```powershell
powershell -File C:\randeman\scripts\backup-daily.ps1 `
  -CenterPath "\\CENTER-SRV\randeman-backup" `
  -PgDumpPath "C:\rosepsy\runtime\pgsql\bin\pg_dump.exe"
```

اسکریپت:
1. `pg_dump -Fc -d randeman` با حساب `randeman_backup` (مجوز فقط‌خواندنی)
2. فشرده‌سازی پوشه مستندات + تنظیمات (بدون .env — اسرار جدا نگه‌داری می‌شوند)
3. ساخت `manifest.json` (فهرست، سایز، SHA256، شناسه نسخه برنامه از `VERSION`، زمان تهیه)
4. انتقال امن به مقصد مرکز + گزارش موفقیت/شکست در لاگ

## بسته پنجشنبه (تحویل هفتگی)

شامل: پشتیبان قابل بازیابی، مستندات سازگار، شناسه نسخه، زمان تهیه، Manifest و فهرست، Hash، گزارش موفقیت انتقال، نتیجه آخرین آزمون بازیابی. انتقال با رمزگذاری/کانال امن؛ Hash به‌تنهایی کنترل اصالت نیست.

## بازیابی (آزمون ماهانه — AC-14)

```powershell
# در محیط پاک:
createdb -h 127.0.0.1 -U randeman_migrator randeman_restore
pg_restore -h 127.0.0.1 -U randeman_migrator -d randeman_restore --no-owner --role=randeman_app randeman_YYYYMMDD.dump
# سپس: جای‌گذاری پوشه مستندات مطابق Manifest و اجرای app + بررسی readyz
```

نتیجه در `backup-staging\restore-test-log.md` ثبت شود.

## نکته RPO یک‌ساعته

طرح Base Backup + آرشیو WAL + PITR اثر بر کل خوشه دارد و نیازمند تأیید مسئول PostgreSQL است؛ بدون آن وعده RPO یک‌ساعته داده نمی‌شود (سند ۱۶.۳).
