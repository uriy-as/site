$domain = "uriy-as.org"
$checkInterval = 120
$notified = $false
$logFile = "$env:TEMP\uriy-as-dns-monitor.log"
$tgToken = "8308743016:AAEwu53QB_rwy5Di40YON4NBZA4A6SbgRQ0"
$tgChat = "1994948658"

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $logFile -Value $line
    Write-Host $line
}

function Send-Telegram {
    param([string]$text)
    try {
        $body = @{ chat_id = $tgChat; text = $text; parse_mode = "HTML" }
        Invoke-RestMethod -Uri "https://api.telegram.org/bot${tgToken}/sendMessage" -Method Post -Body $body -TimeoutSec 10 | Out-Null
    } catch { Write-Log "Telegram send error: $_" }
}

function Invoke-IndexNow {
    param([string]$url)
    try {
        $body = @{ host = $url; key = "7538d0a2a3c64dfeb8733dbf3e6d0617"; keyLocation = "https://${url}/7538d0a2a3c64dfeb8733dbf3e6d0617.txt"; urlList = @("https://${url}/", "https://${url}/services.html", "https://${url}/articles.html") } | ConvertTo-Json
        Invoke-RestMethod -Uri "https://yandex.com/indexnow" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
        Invoke-RestMethod -Uri "https://www.bing.com/indexnow" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 10 | Out-Null
        Write-Log "IndexNow pinged for $url"
    } catch { Write-Log "IndexNow error: $_" }
}

Write-Log "DNS monitor started for $domain"
Send-Telegram "🔍 Мониторинг <b>$domain</b> запущен. Жду когда DNS восстановится…"

while ($true) {
    try {
        $ip = Resolve-DnsName $domain -Type A -Server "8.8.8.8" -ErrorAction Stop
        $ns = Resolve-DnsName $domain -Type NS -Server "8.8.8.8" -ErrorAction SilentlyContinue
        $onHold = ($ns | Where-Object { $_.NameHost -match "namecheap" } | Select-Object -First 1)

        if ($ip.IPAddress -and -not $onHold) {
            if (-not $notified) {
                Write-Log "SITE IS UP! IP: $($ip.IPAddress)"
                Add-Type -AssemblyName System.Windows.Forms
                $notify = New-Object System.Windows.Forms.NotifyIcon
                $notify.Icon = [System.Drawing.SystemIcons]::Information
                $notify.BalloonTipTitle = "$domain открылся!"
                $notify.BalloonTipText = "Сайт доступен по IP $($ip.IPAddress)"
                $notify.Visible = $true
                $notify.ShowBalloonTip(10000)
                Start-Sleep -Seconds 10
                $notify.Visible = $false
                $notified = $true
                Send-Telegram "✅ <b>$domain</b> снова доступен!<code>IP: $($ip.IPAddress)</code>Пингую IndexNow (Yandex + Bing)…"
                Invoke-IndexNow -url $domain
                Start-Sleep -Seconds 5
                Invoke-IndexNow -url "uriy-as.github.io"
                Send-Telegram "✅ IndexNow оправлен. Сайт должен начать индексироваться в ближайшие часы."
            }
        } else {
            if ($notified) { $notified = $false }
            Write-Log "Still on hold"
        }
    }
    catch {
        Write-Log "DNS error: $_"
    }

    Start-Sleep -Seconds $checkInterval
}
