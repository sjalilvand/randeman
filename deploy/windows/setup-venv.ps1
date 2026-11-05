# ساخت محیط مجازی راندمان — deploy/windows/setup-venv.ps1
# Python را در مسیرهای استاندارد و رجیستری (PEP 514) پیدا می‌کند، venv می‌سازد و وابستگی‌ها را نصب می‌کند.
# لازم نیست Python در PATH باشد.
#
# اجرا:
#   powershell -ExecutionPolicy Bypass -File C:\randeman\releases\v1.0.0\deploy\windows\setup-venv.ps1
#
param(
    [string]$VenvDir = "C:\randeman\runtime\venv",
    [string]$ReleaseDir = "C:\randeman\releases\v1.0.0"
)
$ErrorActionPreference = "Stop"

$py = $null
$candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "C:\Program Files\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "C:\Program Files\Python313\python.exe",
    "C:\Windows\py.exe",
    "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe"
)
foreach ($c in $candidates) { if (Test-Path $c) { $py = $c; break } }

if (-not $py) {
    # دقیق‌ترین روش: رجیستری PEP 514 — محل نصب هر Python ثبت‌شده
    foreach ($hive in @("HKCU:\SOFTWARE\Python\PythonCore", "HKLM:\SOFTWARE\Python\PythonCore", "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore")) {
        Get-ChildItem $hive -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not $py) {
                $ip = Get-ItemProperty (Join-Path $_.PSPath "InstallPath") -ErrorAction SilentlyContinue
                if ($ip) {
                    $exe = $ip.ExecutablePath
                    if (-not $exe -and $ip.'(default)') { $exe = Join-Path $ip.'(default)' "python.exe" }
                    if ($exe -and (Test-Path $exe)) { $py = $exe }
                }
            }
        }
    }
}

if (-not $py) {
    throw "Python یافت نشد — از python.org نسخه 3.12 را نصب کنید و در صفحه اول نصب، گزینه Add python.exe to PATH را فعال کنید، سپس این اسکریپت را دوباره اجرا کنید."
}

Write-Host "✅ Python پیدا شد: $py" -ForegroundColor Green
& $py --version
if ($LASTEXITCODE -ne 0) { throw "اجرای Python ناموفق بود." }

Write-Host "ساخت venv در $VenvDir ..."
& $py -m venv $VenvDir
if ($LASTEXITCODE -ne 0) { throw "ساخت venv ناموفق بود." }

$VPython = Join-Path $VenvDir "Scripts\python.exe"
& $VPython -m pip install --upgrade pip --quiet
& $VPython -m pip install -r (Join-Path $ReleaseDir "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "نصب وابستگی‌ها ناموفق بود — اتصال اینترنت سرور بررسی شود." }

Write-Host "`n✅ محیط مجازی آماده است: $VPython" -ForegroundColor Green

if (-not (Test-Path "C:\randeman\config\.env")) {
    New-Item -ItemType Directory -Force -Path "C:\randeman\config" | Out-Null
    Copy-Item (Join-Path $ReleaseDir "backend\.env.example") "C:\randeman\config\.env"
    Write-Host "⚠️ فایل C:\randeman\config\.env از نمونه ساخته شد — رمز واقعی randeman_app را جای CHANGE_ME بگذارید (URL-encode: ! → %21)." -ForegroundColor Yellow
} else {
    Write-Host "فایل تنظیمات موجود است: C:\randeman\config\.env" -ForegroundColor DarkCyan
}

Write-Host "گام بعد: C:\randeman\releases\v1.0.0\deploy\windows\start-randeman.ps1" -ForegroundColor Cyan
