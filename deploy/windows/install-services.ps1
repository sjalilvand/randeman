# اسکریپت نصب سرویس‌های Windows — راندمان
# اجرا با PowerShell 7 و دسترسی Administrator
# پیش‌نیاز: مسیرها ایجاد شده، venv ساخته، requirements نصب، migration اجرا شده باشد

param(
    [string]$Root = "C:\randeman",
    [string]$NssmPath = "C:\rosecenter\tools\nssm.exe",
    [string]$Version = "v1.0.0",
    [string]$ServiceAccount = ".\svc_randeman",
    [SecureString]$ServicePassword = (Read-Host -Prompt "رمز حساب سرویس" -AsSecureString)
)

$ErrorActionPreference = "Stop"
$BackendDir = "$Root\releases\$Version\backend"
$Python = "$Root\runtime\venv\Scripts\python.exe"
$PlainPassword = [System.Net.NetworkCredential]::new("", $ServicePassword).Password

if (-not (Test-Path $NssmPath)) { throw "NSSM یافت نشد: $NssmPath — نسخه و سازگاری بررسی شود" }
if (-not (Test-Path $Python)) { throw "Python venv یافت نشد: $Python" }

function Install-RandemanService($Name, $Arguments, $OutLog, $ErrLog) {
    & $NssmPath stop $Name 2>$null
    & $NssmPath remove $Name confirm 2>$null
    & $NssmPath install $Name $Python $Arguments
    & $NssmPath set $Name AppDirectory $BackendDir
    & $NssmPath set $Name AppStdout $OutLog
    & $NssmPath set $Name AppStderr $ErrLog
    & $NssmPath set $Name AppRotateFiles 1
    & $NssmPath set $Name AppRotateOnline 1
    & $NssmPath set $Name AppRotateBytes 10485760
    & $NssmPath set $Name ObjectName $ServiceAccount $PlainPassword
    & $NssmPath set $Name Start SERVICE_AUTO_START
    # بازیابی پس از خطا: ری‌استارت با تأخیر
    & $NssmPath set $Name AppExit Default Restart
    & $NssmPath set $Name AppRestartDelay 5000
}

# API — مطابق سند ۱۵.۴ (بدون --reload در عملیات)
Install-RandemanService "RandemanAPI" `
    "-m uvicorn app.main:app --host 127.0.0.1 --port 8011 --workers 2" `
    "$Root\logs\api-out.log" "$Root\logs\api-err.log"

# Worker پس‌زمینه — یک سرویس، یک کار سنگین هم‌زمان (سند ۱۴.۱)
Install-RandemanService "RandemanWorker" `
    "-m app.worker" `
    "$Root\logs\worker-out.log" "$Root\logs\worker-err.log"

# ACL مسیرهای داده برای حساب سرویس
@("$Root\data","$Root\logs","$Root\backup-staging") | ForEach-Object {
    icacls $_ /grant:r "${ServiceAccount}:(OI)(CI)M" | Out-Null
}

Write-Host "✅ سرویس‌ها نصب شدند. آغاز:"
Start-Service RandemanAPI
Start-Service RandemanWorker
Get-Service RandemanAPI, RandemanWorker

Write-Host "آزمون سلامت:"
Start-Sleep -Seconds 4
Invoke-RestMethod http://127.0.0.1:8011/healthz | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8011/readyz | ConvertTo-Json
