$ErrorActionPreference = "Stop"

$Root = Join-Path $env:TEMP ("black-magic-harvest-a-monitor-test-" + [Guid]::NewGuid().ToString("N"))
$EvidenceRoot = Join-Path $Root "evidence"
$StopSignal = Join-Path $Root "stop.signal"
$Monitor = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\watch-black-magic-harvest-a.ps1"

try {
    New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
    @(
        '{"external_action_id":"a1"}',
        '{"external_action_id":"a2"}',
        '{"external_action_id":"a3"}'
    ) | Set-Content -Path (Join-Path $EvidenceRoot "external_actions.jsonl") -Encoding UTF8
    '{"status":"OK"}' | Set-Content -Path (Join-Path $EvidenceRoot "integrity.json") -Encoding UTF8
    '{"used":3,"cap":4}' | Set-Content -Path (Join-Path $EvidenceRoot "budget.json") -Encoding UTF8
    New-Item -ItemType File -Force -Path $StopSignal | Out-Null

    $started = [DateTime]::UtcNow.AddSeconds(-10).ToString("o")
    $output = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Monitor `
        -EvidenceRoot $EvidenceRoot `
        -RunId "monitor-test" `
        -StopSignal $StopSignal `
        -TotalActions 4 `
        -BaseActions 3 `
        -RefreshSeconds 1 `
        -StartedAtUtc $started 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "monitor exited $LASTEXITCODE" }
    $text = ($output | Out-String)
    if ($text -notmatch "HARVEST A COMPLETE") { throw "monitor did not report completion" }
    if ($text -notmatch "Final calls:\s+3 / 4") { throw "monitor did not report final call total" }
    if ($text -notmatch "Time left") { throw "monitor did not render time-left field" }
    if ($text -notmatch "ETA") { throw "monitor did not render ETA field" }
    Write-Host "BLACK_MAGIC_HARVEST_A_MONITOR_INTEGRATION_OK"
}
finally {
    if (Test-Path $Root) {
        Start-Sleep -Milliseconds 100
        Remove-Item $Root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
