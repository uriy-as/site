param(
    [string]$Token = "8308743016:AAEwu53QB_rwy5Di40YON4NBZA4A6SbgRQ0",
    [string]$ChatId = "@webstudio_chanel",
    [string]$StateFile = "C:\Users\Admin\.telegram-poster-state.json"
)

$PostsFile = "C:\Users\Admin\Documents\site\.github\scripts\posts.json"

$State = @{ used = @() }
if (Test-Path $StateFile) {
    try { $State = Get-Content $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
}

$Parsed = Get-Content $PostsFile -Raw -Encoding UTF8 | ConvertFrom-Json

if ($null -eq $State.used) { $State.used = @() }
$unused = @()
for ($i = 0; $i -lt $Parsed.Count; $i++) {
    if ($State.used -notcontains $i) { $unused += $i }
}
if ($unused.Count -eq 0) {
    $State.used = @()
    $unused = @(0..($Parsed.Count-1))
}
$nextIdx = $unused[0]
$Post = $Parsed[$nextIdx]

$uri = "https://api.telegram.org/bot$Token/sendMessage"
$body = @{ chat_id = $ChatId; text = $Post[2]; parse_mode = "HTML" }

try {
    $result = Invoke-RestMethod -Uri $uri -Method Post -Body $body
    if ($result.ok) {
        $State.used += $nextIdx
        $State | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8
        Write-Host "Sent: $($Post[1]) (index $nextIdx)"
    }
} catch { Write-Host "FAILED: $_"; exit 1 }
