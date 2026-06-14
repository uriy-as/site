param()

$domain = "uriy-as.org"
$checkInterval = 120
$logFile = "$env:TEMP\uriy-as-dns-monitor.log"
$stateFile = "$env:TEMP\uriy-as-dns-state.json"
$tgToken = "8308743016:AAEwu53QB_rwy5Di40YON4NBZA4A6SbgRQ0"
$tgChat = "1994948658"

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $logFile -Value $line
}

function Send-Telegram {
    param([string]$text)
    try {
        $body = @{ chat_id = $tgChat; text = $text; parse_mode = "HTML" }
        Invoke-RestMethod -Uri "https://api.telegram.org/bot${tgToken}/sendMessage" -Method Post -Body $body -TimeoutSec 10 | Out-Null
    } catch {
        Write-Log ("Telegram send error: " + $_.Exception.Message)
    }
}

function Get-State {
    if (Test-Path $stateFile) {
        try { return (Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json) } catch {}
    }
    return @{ notified = $false; lastStatus = $null }
}

function Save-State {
    param($state)
    $state | ConvertTo-Json | Set-Content $stateFile -Encoding UTF8
}

function Invoke-IndexNow {
    param([string]$url)
    try {
        $key = "7538d0a2a3c64dfeb8733dbf3e6d0617"
        $urls = @("https://${url}/", "https://${url}/services.html", "https://${url}/articles.html")
        $payload = @{ host = $url; key = $key; keyLocation = "https://${url}/${key}.txt"; urlList = $urls }
        $json = $payload | ConvertTo-Json
        Invoke-RestMethod -Uri "https://yandex.com/indexnow" -Method Post -ContentType "application/json" -Body $json -TimeoutSec 10 | Out-Null
        Invoke-RestMethod -Uri "https://www.bing.com/indexnow" -Method Post -ContentType "application/json" -Body $json -TimeoutSec 10 | Out-Null
        Write-Log ("IndexNow pinged for " + $url)
    } catch {
        Write-Log ("IndexNow error: " + $_.Exception.Message)
    }
}

Write-Log "DNS monitor started for $domain"
$state = Get-State

while ($true) {
    try {
        $ipResult = Resolve-DnsName $domain -Type A -Server "8.8.8.8" -ErrorAction SilentlyContinue
        $nsResult = Resolve-DnsName $domain -Type NS -Server "8.8.8.8" -ErrorAction SilentlyContinue
        $onHold = $false
        foreach ($ns in $nsResult) {
            if ($ns.NameHost -match "namecheap") { $onHold = $true }
        }

        if ($ipResult -and (-not $onHold)) {
            $ips = ($ipResult | Select-Object -ExpandProperty IPAddress) -join ", "
            if (-not $state.notified) {
                Write-Log ("SITE IS UP! IP: " + $ips)
                $state.notified = $true
                $state.lastStatus = "up"
                Save-State $state
                Send-Telegram ("SITE IS UP! Domain: $domain IP: $ips")
                Invoke-IndexNow -url $domain
                Start-Sleep -Seconds 5
                Invoke-IndexNow -url "uriy-as.github.io"
                Send-Telegram ("IndexNow sent for Yandex and Bing.")
            }
        } else {
            if ($state.notified) {
                $state.notified = $false
                $state.lastStatus = "down"
                Save-State $state
                Send-Telegram ("Site $domain is DOWN again.")
            }
        }
    }
    catch {
        Write-Log ("DNS monitor error: " + $_.Exception.Message)
    }

    Start-Sleep -Seconds $checkInterval
}
