param([switch]$Remove)

$taskName = "WebStudioPostGenerator"
$ps1Path = "$PSScriptRoot\telegram-poster.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Task '$taskName' removed."
    return
}

# Create a new scheduled task for Mon, Wed, Fri, Sat at 08:00
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ps1Path`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Wednesday, Friday, Saturday -At 08:10
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force

Write-Host "Task '$taskName' created."
Write-Host "Schedule: Mon, Wed, Fri, Sat at 08:00"
Write-Host "Script: $ps1Path"
