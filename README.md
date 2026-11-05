# راندمان — سامانه مدیریت عملکرد، وظایف، پروژه‌ها و مستندات سازمانی

پیاده‌سازی نسخه اولیه قابل بهره‌برداری (MVP) بر اساس «سند جامع نیازمندی‌ها و طراحی نرم‌افزار — نسخه ۲.۰».

> نام مستعار سند: «دیدبان عملکرد» — نام مخزن و محصول: **راندمان**

## معماری (مطابق سند ۹.۳)

```text
React + TypeScript (Vite build → dist)
        │ HTTPS / Same Origin
        ▼
Nginx داخلی سامانه (:8087)
 ├── فایل‌های ساخته‌شده React/Vite
 └── /api/v1 → Uvicorn / FastAPI (:8011)
                    │
                    ├── گردش کار و کنترل دسترسی رکوردی
                    ├── PostgreSQL (پایگاه مستقل randeman)
                    ├── مخزن مستندات (قرنطینه + اسکن ClamAV)
                    └── ممیزی و لاگ

Python Worker مستقل (Windows Service)
 ├── اعلان و یادآوری
 ├── اسکن مستندات
 ├── تولید Excel/PDF
 └── پردازش کارهای پایدار (صف در PostgreSQL با SKIP LOCKED)
```

## فناوری‌ها

| لایه | انتخاب |
|---|---|
| API | FastAPI + Uvicorn |
| مدل/اعتبارسنجی | Pydantic 2 |
| دسترسی داده | SQLAlchemy 2 + Psycopg 3 |
| Migration | Alembic |
| رابط | React 18 + TypeScript + Vite |
| داده سمت رابط | TanStack Query + React Router |
| Excel | openpyxl (محافظت از تزریق فرمول) |
| تقویم | jdatetime (بک‌اند) + jalaali-js (رابط) — نمایش شمسی، ذخیره UTC |
| امنیت رمز | Argon2id + نشست Cookie امن (HttpOnly/SameSite) |
| اسکن فایل | ClamAV (clamd روی 3310) |
| آزمون | pytest (۲۴ سناریو) |

## ساختار مخزن

```text
backend/    سرویس FastAPI، مدل‌ها، سرویس‌های دامنه، Worker، Seed، آزمون‌ها
frontend/   رابط React/TS فارسی RTL (14 صفحه)
deploy/     اسکریپت‌های Windows (NSSM)، پشتیبان‌گیری، Nginx، PostgreSQL
docs/       راهنمای نصب، معماری، پشتیبان‌گیری، سناریوهای پذیرش + ci-workflow.yml
```

> **فعال‌سازی CI:** فایل `docs/ci-workflow.yml` را در مسیر `.github/workflows/ci.yml` قرار دهید (نیازمند توکن با scope «workflow» است).

## داده اولیه (واقعی — جایگزین داده دمو)

```bash
cd backend
python -m app.seed                        # داده واقعی از app/initial_data.json (پیش‌فرض)
python -m app.seed --with-demo            # فقط برای آزمون توسعه: داده نمونه
python -m app.seed --initial-data C:/path/to/initial_data.json   # فایل اختصاصی
```

- `backend/app/initial_data.json` قابل ویرایش است: ۷ واحد سازمانی، ۱۷ کاربر (با جانشین)، **شش پروژه واقعی (RND-P01…P06)** و ۱۹ وظیفه. اجرا idempotent است.
- رمز اولیه همه حساب‌ها: `Randeman@1404` — پیش از بهره‌برداری تغییر کند (تصمیم ۲۵.۲).
- حساب مدیر سامانه: `admin`

## شروع سریع (توسعه)

```bash
# بک‌اند
cd backend
python -m venv .venv && .venv\Scripts\activate      # ویندوز
pip install -r requirements.txt
alembic upgrade head                                 # ایجاد ساختار پایگاه
python -m app.seed                                   # داده واقعی سازمان
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011

# Worker (پنجره دیگر)
python -m app.worker

# فرانت‌اند
cd frontend
npm ci
npm run dev        # پروکسی /api به پورت 8011
```

آدرس‌ها: رابط `http://localhost:5173` — OpenAPI `http://127.0.0.1:8011/docs`

## راه‌اندازی روی سرور — پورت 8095 (تک‌پورت)

ابتدا بسته را مستقیم از گیت‌هاب بگیرید (رابط ساخته‌شده `frontend/dist` هم در مخزن است — نیازی به Node روی سرور نیست):

```powershell
git clone https://github.com/sjalilvand/randeman.git C:\randeman\releases\v1.0.0   # اگر مسیر خالی/ناموجود است
# به‌روزرسانی بعدی:  git -C C:\randeman\releases\v1.0.0 pull
# اگر مسیر از قبل چیزی دارد: docs/01-INSTALL-WINDOWS.md بخش ۲ب
```

سپس پس از اجرای docs/01-INSTALL-WINDOWS.md (venv، پایگاه، config\.env):

```powershell
# PowerShell 7 روی Windows Server:
C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1            # شروع روی 8095
C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1 -Status     # وضعیت + آزمون سلامت (PostgreSQL/ClamAV/API)
C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1 -Stop       # توقف
C:\randeman\releases\v1.0.0\deploy\windows\test-clamav.ps1                # آزمون ClamAV پورت 3310 (PING/OK/EICAR)
```

حالت تک‌پورت 8095، رابط React ساخته‌شده و API را هم‌زمان ارائه می‌دهد (`RANDEMAN_SERVE_DIST_DIR`). برای عملیات پایدار با HTTPS، معماری سند ۱۵ (Caddy:443 → Nginx:8087 → API:8011) مبنا است.

## آزمون سلامت (سند ۱۵.۸)

```bash
curl http://127.0.0.1:8095/healthz   # {"status":"ok"}
curl http://127.0.0.1:8095/readyz    # وضعیت db، ضربان Worker و دسترس‌پذیری ClamAV 3310
```

گزارش کامل تصمیم‌های مدیریتی (دامنه HTTPS، مهلت گزارش، RPO/RTO و…): `docs/04-DECISIONS-25-2.md`

## پایگاه داده

- توسعه: SQLite (پیش‌فرض) — بدون نیاز به نصب
- عملیات: PostgreSQL موجود (نسخه 16.15 گزارش‌شده) با پایگاه مستقل `randeman` و حساب‌های تفکیک‌شده (`randeman_app`, `randeman_migrator`, `randeman_report`, `randeman_backup`) — اسکریپت: `deploy/postgres/01-create-database.sql`
- Migration: `alembic upgrade head` با حساب migrator — **در شروع Worker اجرای خودکار انجام نمی‌شود** (سند ۱۵.۶)

## استقرار روی Windows Server

راهنمای کامل: `docs/01-INSTALL-WINDOWS.md`

خلاصه: مسیر `C:\randeman\`، محیط venv مستقل، سرویس‌های `RandemanAPI` و `RandemanWorker` با NSSM، Nginx داخلی روی `127.0.0.1:8087` با خروجی `frontend/dist`، و ورودی HTTPS موجود (Caddy/ورودی سازمان) به‌صورت پراکسی به 8087 — بدون تعارض با پورت‌های اشغال.

## امنیت

- کنترل دسترسی **رکوردی** در FastAPI (نقش + محدوده سازمانی + عضویت پروژه)؛ رکورد غیرمجاز با 404 پاس می‌شود
- CSRF: الزام سربرگ `X-Requested-With` برای همه عملیات تغییردهنده
- محدودیت تلاش ناموفق ورود (۵ تلاش → قفل ۱۵ دقیقه) + ثبت ممیزی ورود ناموفق
- فایل: قرنطینه → اعتبارسنجی (پسوند/حجم/امضا) → اسکن clamd → آماده/رد؛ عدم دسترسی اسکن ⇒ ماندن در قرنطینه
- رمزها Argon2id؛ نشست سمت سرور با ابطال
- ⚠️ **توکن گیت‌هاب هرگز در کد/تنظیمات نگه‌داری نشود** — اگر توکنی در گفتگو یا ایمیل به اشتراک گذاشته شده، فوراً باطل (Revoke) شود.

## پشتیبان‌گیری

روزانه `pg_dump` قالب Custom + بسته مستندات + Manifest و Hash؛ تحویل پنجشنبه با انتقال امن. راهنما: `docs/02-BACKUP-RESTORE.md` و اسکریپت `deploy/windows/backup-daily.ps1`

## پوشش سند — نسخه اولیه (سند ۲۰)

| ماژول | وضعیت |
|---|---|
| کاربران، نقش‌ها، ساختار سازمانی | ✅ |
| پروژه + اعضا + نقاط عطف | ✅ |
| وظیفه + گردش تأیید + تاریخچه + درخواست تغییر سررسید | ✅ |
| فعالیت‌ها | ✅ |
| گزارش هفتگی نسخه‌بندی‌شده | ✅ |
| مستندات امن + قرنطینه + اسکن + نسخه‌بندی | ✅ |
| موانع + ریسک + درخواست تصمیم | ✅ |
| داشبورد فردی/واحدی/پروژه‌ای/سازمانی | ✅ |
| شاخص‌های سند ۷ با «غیرقابل محاسبه» برای مخرج صفر | ✅ |
| اعلان داخلی + یادآوری در Worker | ✅ |
| خروجی Excel (روی خطا + صف) | ✅ |
| ممیزی | ✅ |
| Worker مستقل + صف PostgreSQL | ✅ |
| PDF فارسی (Chromium در Worker) | 🔜 فاز ۵ |
| ورود از Excel، Gantt، گزارش‌ساز آزاد | 🔜 فاز ۵ |

## انحراف‌های مستند از سند (برای تصویب کارفرما)

1. نام محصول در کد/پایگاه/سرویس‌ها «randeman» به‌جای «didban» — مطابق نام مخزن؛ با متغیرهای پیکربندی قابل تغییر است.
2. در MVP، «درخواست تصمیم» داخل همان رکورد «مانع» مدل شده (فیلد decision_needed) به‌جای جدول جداگانه.
3. اعداد اعشاری (وزن/ساعت) با Float ذخیره می‌شوند (به‌جای Numeric) — در نسخه بعد با Numeric دقیق می‌شود.
4. ایمیل اعلان‌ها وابسته به SMTP است و در MVP در صف علامت می‌خورد؛ کانال پیام‌سامانه توسعه آتی.
5. مبنای محاسبه «تکمیل به‌موقع» سررسید جاری/مبنا و «تأخیر» روز تقویمی است؛ در هر گزارش عنوان می‌شود (قابل تبدیل به روز کاری پس از تعریف تقویم).

## مجوزها و مالکیت

تمام حقوق برای کارفرما محفوظ است. حساب مخفی، در پشتی و وابستگی اعلام‌نشده وجود ندارد.
