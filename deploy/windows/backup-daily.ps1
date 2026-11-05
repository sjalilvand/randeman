# پشتیبان‌گیری روزانه راندمان — pg_dump + مستندات + Manifest + انتقال مرکز
# زمان‌بندی: Task Scheduler ساعت کم‌بار (مثلاً 01:30)

param(
    [string]$Root = "C:\randeman",
    [string]$PgDumpPath = "C:\rosepsy\runtime\pgsql\bin\pg_dump.exe",
    [string]$CenterPath = "\\CENTER-SRV\randeman-backup",
    [string]$DbUser = "randeman_backup",
    [string]$DatabaseName = "randeman"
)

$ErrorActionPreference = "Stop"
$Stamp = Get-Date -Format "yyyyMMdd-HHmm"
$IsThursday = (Get-Date).DayOfWeek -eq [System.DayOfWeek]::Thursday
$BackupDir = "$Root\backup-staging\$Stamp"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Log = "$Root\logs\backup.log"

function Log($msg) {
    "$(Get-Date -Format o) $msg" | Tee-Object -FilePath $Log -Append
}

# رمز حساب پشتیبان از فایل محافظت‌شده خوانده می‌شود (نه در کد)
$PassFile = "$Root\config\backup-db-pass.txt"
if (-not (Test-Path $PassFile)) { throw "فایل رمز پشتیبان یافت نشد: $PassFile" }
$env:PGPASSWORD = (Get-Content $PassFile -Raw).Trim()

Log "=== شروع پشتیبان‌گیری $Stamp (پنجشنبه: $IsThursday) ==="

# ۱) پشتیبان منطقی دیتابیس (قالب Custom)
$Dump = "$BackupDir\randeman-$Stamp.dump"
& $PgDumpPath -h 127.0.0.1 -U $DbUser -Fc -d $DatabaseName -f $Dump
if ($LASTEXITCODE -ne 0) { Log "❌ pg_dump ناموفق"; throw "pg_dump failed" }
Log "✅ pg_dump: $((Get-Item $Dump).Length / 1MB -as [int]) MB"

# ۲) مستندات و نسخه‌های فایل
$DocsZip = "$BackupDir\documents-$Stamp.zip"
Compress-Archive -Path "$Root\data\documents\*","$Root\data\quarantine\*" -DestinationPath $DocsZip -Force
Log "✅ مستندات فشرده شد"

# ۳) تنظیمات (بدون اسرار)
Copy-Item "$Root\config\*.json","$Root\config\*.yml" -Destination $BackupDir -ErrorAction SilentlyContinue

# ۴) شناسه نسخه برنامه
Set-Content -Path "$BackupDir\VERSION" -Value (Get-Content "$Root\releases\current-VERSION" -ErrorAction SilentlyContinue ?? "unknown")

# ۵) Manifest + Hash
$manifest = @{
    created_at = (Get-Date -Format o)
    database   = @{ name = $DatabaseName; file = (Split-Path $Dump -Leaf); sha256 = (Get-FileHash $Dump -Algorithm SHA256).Hash }
    documents  = @{ file = (Split-Path $DocsZip -Leaf); sha256 = (Get-FileHash $DocsZip -Algorithm SHA256).Hash }
    delivery   = @{ is_thursday_package = $IsThursday }
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content "$BackupDir\manifest.json"
Log "✅ Manifest ساخته شد"

# ۶) انتقال امن به مرکز
try {
    robocopy $BackupDir "$CenterPath\$Stamp" /MIR /R:2 /W:5 | Out-Null
    if ($LASTEXITCODE -le 7) { Log "✅ انتقال به مرکز موفق: $CenterPath\$Stamp" }
    else { throw "robocopy exit $LASTEXITCODE" }
} catch {
    Log "❌ انتقال به مرکز ناموفق: $_ — نسخه محلی در $BackupDir باقی است"
    exit 1
}

Log "=== پایان موفق ==="
