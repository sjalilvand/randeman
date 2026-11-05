# راهنمای نصب و استقرار روی Windows Server 2025 (سند ۱۵)

> همه دستورات در PowerShell 7 اجرا شوند. تغییر سامانه‌های موجود (rosepsy، survey-system، Caddy، Nginx موجود) ممنوع است.

## ۱. پیش‌نیازها

- [ ] تأیید DNS و مسیر ورودی HTTPS (تعارض Caddy روی 80 بررسی شده باشد)
- [ ] PostgreSQL موجود روی 5432 فعال و نسخه آن با پرس‌وجوی مجاز تأیید شده باشد
- [ ] ClamAV روی 3310 در دسترس (`Test-NetConnection 127.0.0.1 -Port 3310`)
- [ ] فایروال: پورت‌های 8011 و 8087 فقط روی localhost/داخلی؛ 5432/6379/3310/3389/WinRM از اینترنت بسته
- [ ] Python 3.12، Node.js (فقط برای build)، NSSM در `C:\rosecenter\tools\nssm.exe` (نسخه بررسی شود)

## ۲. ساختار مسیرها

```powershell
$Root = "C:\randeman"
$dirs = @("$Root\releases\v1.0.0\backend","$Root\releases\v1.0.0\frontend","$Root\runtime\venv",
          "$Root\config","$Root\data\documents","$Root\data\quarantine","$Root\data\exports",
          "$Root\data\temp","$Root\logs","$Root\scripts","$Root\backup-staging")
$dirs | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
```

بسته انتشار (خروجی CI یا build محلی) داخل `releases\v1.0.0` باز شود؛ `runtime\venv` مستقل می‌ماند.

## ۳. محیط مجازی مستقل

```powershell
py -3.12 -m venv C:\randeman\runtime\venv
C:\randeman\runtime\venv\Scripts\python.exe -m pip install --upgrade pip
C:\randeman\runtime\venv\Scripts\pip.exe install -r C:\randeman\releases\v1.0.0\backend\requirements.txt
```

> هرگز در venv سامانه‌های دیگر (C:\rosepsy\runtime\venv یا C:\survey-system\venv) نصب نشود.

## ۴. پایگاه داده و حساب‌ها

با حساب مدیر PostgreSQL اسکریپت `deploy\postgres\01-create-database.sql` را اجرا کنید (مقادیر رمز را پارامتری کنید):

```powershell
$env:PGPASSWORD = "<postgres-admin-password>"
& "C:\rosepsy\runtime\pgsql\bin\psql.exe" -h 127.0.0.1 -U postgres -v app_pw="'...'" -v migrator_pw="'...'" -f C:\randeman\releases\v1.0.0\deploy\postgres\01-create-database.sql
```

سپس Migration با حساب migrator:

```powershell
cd C:\randeman\releases\v1.0.0\backend
$env:RANDEMAN_DATABASE_URL = "postgresql+psycopg://randeman_migrator:...@127.0.0.1:5432/randeman"
C:\randeman\runtime\venv\Scripts\python.exe -m alembic upgrade head
```

پس از Migration، مجوزهای DML با اسکریپت دوم اعمال می‌شود:

```powershell
& "C:\rosepsy\runtime\pgsql\bin\psql.exe" -h 127.0.0.1 -U postgres -d randeman -f C:\randeman\releases\v1.0.0\deploy\postgres\02-post-migration-grants.sql
```

> این اسکریپت پس از هر Migration آینده نیز باید اجرا شود. سپس داده اولیه واقعی: `python -m app.seed` (فایل `backend\app\initial_data.json` — ۷ واحد، ۱۷ کاربر، شش پروژه RND-P01…P06).

## ۵. پیکربندی

`config\.env` را از `.env.example` بسازید و مقادیر را تنظیم کنید. سپس:

```powershell
# ACL محدود روی فایل تنظیمات
icacls C:\randeman\config\.env /inheritance:r /grant:r "svc_randeman:(R)" "Administrators:(F)"
```

اسرار فقط همین‌جا باشند؛ متغیر محیطی مخزن امن نیست.

## ۶. ساخت رابط (ترجیحاً در CI)

```powershell
cd C:\randeman\releases\v1.0.0\frontend
npm ci
npm run build       # خروجی dist
```

## ۷. سرویس‌های Windows با NSSM

اسکریپت آماده: `deploy\windows\install-services.ps1` (با حساب سرویس غیر-Administrator اجرا شود):

```powershell
# دستی:
& C:\rosecenter\tools\nssm.exe install RandemanAPI "C:\randeman\runtime\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 127.0.0.1 --port 8011 --workers 2"
& C:\rosecenter\tools\nssm.exe set RandemanAPI AppDirectory C:\randeman\releases\v1.0.0\backend
& C:\rosecenter\tools\nssm.exe set RandemanAPI AppStdout C:\randeman\logs\api-out.log
& C:\rosecenter\tools\nssm.exe set RandemanAPI AppStderr C:\randeman\logs\api-err.log
& C:\rosecenter\tools\nssm.exe set RandemanAPI AppRotateFiles 1
& C:\rosecenter\tools\nssm.exe set RandemanAPI ObjectName ".\svc_randeman" "<رمز حساب سرویس>"
& C:\rosecenter\tools\nssm.exe set RandemanAPI Start SERVICE_AUTO_START

& C:\rosecenter\tools\nssm.exe install RandemanWorker "C:\randeman\runtime\venv\Scripts\python.exe" "-m app.worker"
& C:\rosecenter\tools\nssm.exe set RandemanWorker AppDirectory C:\randeman\releases\v1.0.0\backend
& C:\rosecenter\tools\nssm.exe set RandemanWorker AppStdout C:\randeman\logs\worker-out.log
& C:\rosecenter\tools\nssm.exe set RandemanWorker AppStderr C:\randeman\logs\worker-err.log
```

`--reload` در عملیات فعال نمی‌شود. بازیابی پس از خطا و چرخش لاگ تنظیم شده است.

## ۸. Nginx داخلی سامانه (سایت مستقل)

فایل `deploy\nginx\randeman.conf` را در `conf` نسخه Nginx موجود include کنید (پس از `nginx -t`):

- listen `127.0.0.1:8087`
- ریشه: `C:/randeman/releases/v1.0.0/frontend/dist`
- `/api/v1` → `http://127.0.0.1:8011`
- `client_max_body_size 25m` (سقف فایل ۲۰MB + سربار multipart)

### همزیستی با Caddy (الگوی ترجیحی سند ۱۵.۳)

در Caddy فقط یک reverse_proxy به 8087 اضافه می‌شود؛ Caddy همچنان 80/443 را دارد:

```caddyfile
randeman.internal.example.ir {
    reverse_proxy 127.0.0.1:8087
}
```

پراکسی باید `X-Forwarded-For` و `X-Forwarded-Proto` را بفرستد؛ `RANDEMAN_TRUSTED_PROXIES` فقط آدرس پراکسی شناخته‌شده است.

## ۹. آزمون پس از نصب

1. `curl http://127.0.0.1:8011/healthz` → ok
2. `curl http://127.0.0.1:8011/readyz` → وضعیت db، Worker و **ClamAV (پورت 3310)**
3. آزمون کامل آنتی‌ویروس: `deploy\windows\test-clamav.ps1` (PING → PONG، فایل سالم → OK، نمونه EICAR → FOUND)
4. ورود با حساب مدیر سامانه، ایجاد کاربر، ایجاد وظیفه، بارگذاری فایل تستی (EICAR رد شود، PDF سالم آماده شود)
5. توقف RandemanAPI برای ۳۰ ثانیه — Worker نباید متوقف شود (AC-13)
6. اجرای `backup-daily.ps1` و یک بازیابی آزمایشی در محیط پاک (AC-14)

## ۱۰. راه‌اندازی سریع روی پورت 8095 (تک‌پورت — تصمیم ضمیمه ۲۵.۲)

برای بالا آوردن کل برنامه (رابط + API) از یک پورت، بدون Nginx:

```powershell
& C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1              # شروع
& C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1 -Status      # وضعیت و آزمون سلامت
& C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1 -Stop        # توقف
```

- اسکریپت تنظیمات را از `config\.env` می‌خواند، `RANDEMAN_SERVE_DIST_DIR` را به مسیر dist رابط تنظیم می‌کند و Uvicorn را روی `0.0.0.0:8095` با ۲ Worker اجرا می‌کند.
- در فایروال، پورت 8095 فقط برای محدوده داخلی باز شود (تصمیم ۲۵.۲ — دسترسی شبکه داخلی/VPN).
- این حالت جایگزین معماری عملیاتی (Caddy→Nginx 8087→API 8011) نیست؛ برای HTTPS سازمانی همان مسیر سند ۱۵.۳ مبنا است.
