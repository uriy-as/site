$PosterScript = "C:\Users\Admin\Documents\site\telegram-poster.ps1"
$StateFile = "C:\Users\Admin\.telegram-poster-state.json"
$LastRunFile = "$StateFile.lastrun"
$LockFile = "$env:TEMP\scheduler-launcher.lock"
$LogFile = "$env:TEMP\scheduler-launcher.log"

function Write-Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogFile -Value $line
}

function Rotate-Log {
    $lines = Get-Content -Path $LogFile -ErrorAction SilentlyContinue
    if ($lines.Count -gt 200) {
        $lines[-100..-1] | Set-Content -Path $LogFile -Encoding UTF8
    }
}

function Acquire-Lock {
    if (Test-Path $LockFile) {
        $lockedPid = Get-Content $LockFile -Raw
        if (Get-Process -Id $lockedPid -ErrorAction SilentlyContinue) {
            Write-Log "Lock held by PID $lockedPid - exiting"
            exit
        }
    }
    $pid | Set-Content -Path $LockFile -Encoding UTF8 -Force
}

function Release-Lock {
    if (Test-Path $LockFile) { Remove-Item -Path $LockFile -Force }
}

function Test-Internet {
    try {
        $r = [System.Net.WebRequest]::Create('https://api.telegram.org')
        $r.Timeout = 5000; $r.GetResponse().Close(); return $true
    } catch { return $false }
}

function Restore-StateFile {
    $backup = $StateFile + ".bak"
    if (-not (Test-Path $StateFile) -and (Test-Path $backup)) {
        Copy-Item -Path $backup -Destination $StateFile -Force
        Write-Log "Restored state from backup"
    }
}

function Send-Today {
    param([string]$today)
    if (-not (Test-Internet)) {
        Write-Log "No internet - skipping"
        return
    }
    try {
        & $PosterScript
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            Write-Log "Poster exited with code $LASTEXITCODE"
            return
        }
        [System.IO.File]::WriteAllText($LastRunFile, $today, [System.Text.Encoding]::UTF8)
        Write-Log "Post sent for $today"
    } catch {
        Write-Log "Post error: $($_.Exception.Message)"
    }
}

Acquire-Lock
Write-Log "Started (PID $pid)"
Restore-StateFile

$todaySentInMemory = $null

while ($true) {
    Rotate-Log
    $now = Get-Date
    $today = $now.Date.ToString("yyyy-MM-dd")
    $dayOfWeek = $now.DayOfWeek

    $isScheduledDay = $dayOfWeek -in @([DayOfWeek]::Monday, [DayOfWeek]::Wednesday, [DayOfWeek]::Friday, [DayOfWeek]::Saturday)

    if ($isScheduledDay -and $todaySentInMemory -ne $today) {
        $lastRun = $null
        if (Test-Path $LastRunFile) { $lastRun = (Get-Content $LastRunFile -Raw -Encoding UTF8).Trim() }
        if ($lastRun -ne $today) {
            Restore-StateFile
            Send-Today $today
            $todaySentInMemory = $today
        } else {
            $todaySentInMemory = $today
        }
    }

    if (-not $isScheduledDay) {
        $todaySentInMemory = $null
    }

    Start-Sleep -Seconds 120
}

Release-Lock