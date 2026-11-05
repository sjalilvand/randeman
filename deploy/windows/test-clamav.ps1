# آزمون ClamAV (clamd) روی پورت 3310 — پروتکل zINSTREAM (سند ۵.۶ و تصمیم ۲۵.۲)
# اجرا در PowerShell 7 روی سرور:
#   .\deploy\windows\test-clamav.ps1              # پیش‌فرض: 127.0.0.1:3310
#   .\deploy\windows\test-clamav.ps1 -Host 10.0.0.5 -Port 3310
# خروجی مورد انتظار:
#   PING            → PONG
#   فایل سالم       → stream: OK
#   فایل EICAR      → FOUND (رد می‌شود و در قرنطینه می‌ماند)

param(
    [string]$Host_ = "127.0.0.1",
    [int]$Port = 3310,
    [int]$TimeoutSec = 20
)

$ErrorActionPreference = "Stop"
# رشته آزمون استاندارد EICAR — فقط برای آزمون آنتی‌ویروس؛ هیچ فایلی آلوده نیست
$Eicar = 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'

function Send-Instream([byte[]]$Payload) {
    $client = [System.Net.Sockets.TcpClient]::new($Host_, $Port)
    $client.ReceiveTimeout = $TimeoutSec * 1000
    $client.SendTimeout = $TimeoutSec * 1000
    try {
        $stream = $client.GetStream()
        $cmd = [System.Text.Encoding]::ASCII.GetBytes("zINSTREAM`0")
        $stream.Write($cmd, 0, $cmd.Length)

        # ارسال با قطعه‌های ۸ کیلوبایتی مطابق پروتکل
        $offset = 0
        while ($offset -lt $Payload.Length) {
            $size = [Math]::Min(8192, $Payload.Length - $offset)
            $lenBytes = [BitConverter]::GetBytes([uint32]$size)
            if ([BitConverter]::IsLittleEndian) { [Array]::Reverse($lenBytes) }
            $stream.Write($lenBytes, 0, 4)
            $stream.Write($Payload, $offset, $size)
            $offset += $size
        }
        $stream.Write([BitConverter]::GetBytes([uint32]0), 0, 4)

        $buf = New-Object byte[] 4096
        $n = $stream.Read($buf, 0, $buf.Length)
        return ([System.Text.Encoding]::ASCII.GetString($buf, 0, $n)).Trim("`0")
    } finally { $client.Close() }
}

# ۱) PING — دسترس‌پذیری
$tcp = Test-NetConnection $Host_ -Port $Port -WarningAction SilentlyContinue
if (-not $tcp.TcpTestSucceeded) {
    Write-Host "❌ ClamAV در دسترس نیست: $Host_`:$Port بسته است — فایل‌ها در قرنطینه می‌مانند (سند ۵.۶)" -ForegroundColor Red
    exit 1
}
Write-Host "✅ پورت $Host_`:$Port باز است" -ForegroundColor Green

$ping = [System.Net.Sockets.TcpClient]::new($Host_, $Port)
try {
    $s = $ping.GetStream(); $c = [System.Text.Encoding]::ASCII.GetBytes("zPING`0")
    $s.Write($c, 0, $c.Length); $b = New-Object byte[] 64; $n = $s.Read($b, 0, 64)
    $pong = ([System.Text.Encoding]::ASCII.GetString($b, 0, $n)).Trim("`0")
} finally { $ping.Close() }
if ($pong -ne "PONG") { Write-Host "❌ پاسخ PING غیرمنتظره: $pong" -ForegroundColor Red; exit 1 }
Write-Host "✅ clamd PING → PONG" -ForegroundColor Green

# ۲) فایل سالم (متن UTF-8)
$benign = [System.Text.Encoding]::UTF8.GetBytes("آزمون سلامت اسکن راندمان - فایل سالم")
$r1 = Send-Instream $benign
if ($r1 -match "OK") { Write-Host "✅ فایل سالم → $r1" -ForegroundColor Green }
else { Write-Host "❌ فایل سالم رد شد: $r1" -ForegroundColor Red; exit 1 }

# ۳) فایل EICAR (باید FOUND شود)
$eicarBytes = [System.Text.Encoding]::ASCII.GetBytes($Eicar)
$r2 = Send-Instream $eicarBytes
if ($r2 -match "FOUND") { Write-Host "✅ نمونه EICAR شناسایی و رد شد → $r2" -ForegroundColor Green }
else { Write-Host "❌ هشدار: EICAR شناسایی نشد (پاسخ: $r2) — پایگاه امضای clamd به‌روز نیست" -ForegroundColor Red; exit 1 }

Write-Host "`n✅ آزمون ClamAV کامل شد — سامانه می‌تواند مستندات را اسکن کند." -ForegroundColor Green
