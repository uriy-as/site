$PosterScript = "C:\Users\Admin\Documents\site\telegram-poster.ps1"
$StateFile = "C:\Users\Admin\.telegram-poster-state.json"
$LastRunFile = "$StateFile.lastrun"
$LogFile = "$env:TEMP\scheduler-launcher.log"

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogFile -Value $line
}

function Send-Today {
    param([string]$today)
    try {
        & $PosterScript
        $today | Set-Content -Path $LastRunFile -Encoding UTF8 -Force
        Write-Log ("Post sent for " + $today)
    } catch {
        Write-Log ("Post error: " + $_.Exception.Message)
    }
}

Write-Log "Started"

while ($true) {
    $now = Get-Date
    $today = $now.Date.ToString("yyyy-MM-dd")
    $dayOfWeek = $now.DayOfWeek

    $isScheduledDay = $dayOfWeek -in @([DayOfWeek]::Monday, [DayOfWeek]::Wednesday, [DayOfWeek]::Friday, [DayOfWeek]::Saturday)

    $lastRun = $null
    if (Test-Path $LastRunFile) { $lastRun = Get-Content $LastRunFile -Raw -Encoding UTF8 }

    if ($isScheduledDay -and $lastRun -ne $today) {
        Send-Today $today
    }

    Start-Sleep -Seconds 120
}
