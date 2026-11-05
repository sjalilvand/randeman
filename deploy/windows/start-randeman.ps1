# راه‌اندازی سامانه راندمان روی پورت 8095 — حالت تک‌پورت (رابط + API از یک پورت)
# تصمیم ۲۵.۲ ضمیمه + سند ۱۵.۸ — اجرا در PowerShell 7:
#
#   .\deploy\windows\start-randeman.ps1                    # شروع (پورت 8095)
#   .\deploy\windows\start-randeman.ps1 -Status            # وضعیت و آزمون سلامت
#   .\deploy\windows\start-randeman.ps1 -Stop              # توقف
#   .\deploy\windows\start-randeman.ps1 -Port 8095 -BindAddress "0.0.0.0"
#
# پیش‌نیاز (docs/01-INSTALL-WINDOWS.md):
#   C:\randeman\releases\<نسخه>\backend   کد بک‌اند
#   C:\randeman\releases\<نسخه>\frontend\dist   رابط ساخته‌شده (npm run build)
#   C:\randeman\runtime\venv              محیط مجازی مستقل
#   C:\randeman\config\.env               تنظیمات (RANDEMAN_DATABASE_URL و ...)
#   PostgreSQL موجود روی 127.0.0.1:5432   پایگاه مستقل randeman
#   ClamAV موجود روی 127.0.0.1:3310       اسکن مستندات (در دسترس نبودن = قرنطینه)

param(
    [string]$Root = "C:\randeman",
    [string]$Version = "v1.0.0",
    [int]$Port = 8095,
    [string]$BindAddress = "0.0.0.0",
    [string]$EnvFile = "C:\randeman\config\.env",
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$BackendDir = "$Root\releases\$Version\backend"
$Python = "$Root\runtime\venv\Scripts\python.exe"
$DistDir = "$Root\releases\$Version\frontend\dist"
$PidFile = "$Root\runtime\api-8095.pid"
$OutLog = "$Root\logs\api-8095-out.log"
$ErrLog = "$Root\logs\api-8095-err.log"

function Show-Status {
    Write-Host "`n=== وضعیت راندمان (پورت $Port) ===" -ForegroundColor Cyan
    $pg = Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
    Write-Host ("PostgreSQL 5432 : " + $(if ($pg.TcpTestSucceeded) { "✅ فعال" } else { "❌ قطع" }))
    $clam = Test-NetConnection 127.0.0.1 -Port 3310 -WarningAction SilentlyContinue
    Write-Host ("ClamAV 3310     : " + $(if ($clam.TcpTestSucceeded) { "✅ فعال" } else { "⚠️ در دسترس نیست — فایل‌ها در قرنطینه می‌مانند" }))
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:$Port/healthz" -TimeoutSec 5
        Write-Host "API healthz     : ✅ $($h.status)" -ForegroundColor Green
        $r = Invoke-RestMethod "http://127.0.0.1:$Port/readyz" -TimeoutSec 5
        Write-Host ("API readyz      : " + $r.status + " | worker=" + $r.worker_alive + " | clamav=" + $r.clamav.available)
    } catch {
        Write-Host "API             : ❌ پاسخ نمی‌دهد (در حال اجرا نیست؟)" -ForegroundColor Red
    }
    Write-Host "آدرس رابط: http://<این-سرور>:$Port" -ForegroundColor Cyan
}

if ($Status) { Show-Status; exit 0 }

if ($Stop) {
    if (Test-Path $PidFile) {
        $procId = Get-Content $PidFile
        try { Stop-Process -Id $procId -Force -ErrorAction Stop; Write-Host "✅ فرایند $procId متوقف شد." -ForegroundColor Green }
        catch { Write-Host "فرایند $procId از قبل بسته است." }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    } else {
        Write-Host "فایل PID یافت نشد — سرویس با NSSM نصب شده؟ (Stop-Service RandemanAPI)"
    }
    exit 0
}

# --- اعتبارسنجی پیش‌نیازها ---
if (-not (Test-Path $Python)) { throw "Python venv یافت نشد: $Python — بخش ۳ سند نصب اجرا شود" }
if (-not (Test-Path $BackendDir)) { throw "بک‌اند یافت نشد: $BackendDir" }
if (-not (Test-Path $DistDir)) { Write-Warning "رابط ساخته‌شده یافت نشد: $DistDir — فقط API بالا می‌آید. برای رابط: npm run build در frontend" }
if (-not (Test-Path $EnvFile)) { throw "فایل تنظیمات یافت نشد: $EnvFile — از .env.example بسازید" }

$pg = Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
if (-not $pg.TcpTestSucceeded) { throw "PostgreSQL روی 127.0.0.1:5432 در دسترس نیست — پایگاه randeman و حساب‌ها ساخته شده باشند (بخش ۴ سند نصب)" }

# --- بارگذاری تنظیمات از فایل .env (اسرار فقط همین‌جا) ---
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*RANDEMAN_([A-Z0-9_]+)\s*=\s*(.*)\s*$') {
        [System.Environment]::SetEnvironmentVariable("RANDEMAN_$($Matches[1])", $Matches[2], "Process")
    }
}
# حالت تک‌پورت: ارائه رابط ساخته‌شده از همان پورت API
[System.Environment]::SetEnvironmentVariable("RANDEMAN_SERVE_DIST_DIR", $DistDir, "Process")

# --- جلوگیری از اجرای دوباره ---
if (Test-Path $PidFile) {
    $oldId = Get-Content $PidFile
    if (Get-Process -Id $oldId -ErrorAction SilentlyContinue) {
        Write-Host "⚠️ راندمان از قبل روی پورت $Port اجراست (PID $oldId) — وضعیت: -Status، توقف: -Stop" -ForegroundColor Yellow
        exit 0
    }
}

# --- شروع ---
New-Item -ItemType Directory -Force -Path "$Root\logs", "$Root\runtime" | Out-Null
$proc = Start-Process -FilePath $Python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $BindAddress, "--port", "$Port", "--workers", "2" `
    -WorkingDirectory $BackendDir -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
Set-Content -Path $PidFile -Value $proc.Id
Write-Host "✅ راندمان در حال بالا آمدن روی پورت $Port ... (PID $($proc.Id))" -ForegroundColor Green

# --- آزمون پس از نصب (سند ۱۵.۸) ---
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-RestMethod "http://127.0.0.1:$Port/healthz" -TimeoutSec 2 | Out-Null; $ok = $true; break } catch { }
}
if ($ok) {
    Write-Host "✅ API بالا آمد." -ForegroundColor Green
    Show-Status
    Write-Host "`nورود اولیه: admin / Randeman@1404 — پس از نخستین ورود رمز عوض شود (تصمیم ۲۵.۲)" -ForegroundColor Yellow
} else {
    Write-Host "❌ API پاسخ نداد — لاگ: $ErrLog" -ForegroundColor Red
    Get-Content $ErrLog -Tail 25
    exit 1
}
