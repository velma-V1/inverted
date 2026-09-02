param(
    [Parameter(Mandatory = $true)][string]$EvidenceRoot,
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$StopSignal,
    [int]$TotalActions = 1200,
    [int]$BaseActions = 900,
    [int]$RefreshSeconds = 2,
    [string]$StartedAtUtc
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

function Get-LineCount([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $count = 0
    $reader = $null
    try {
        $reader = [System.IO.File]::OpenText($Path)
        while ($null -ne $reader.ReadLine()) { $count++ }
    }
    catch { }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
    }
    return $count
}

function Format-Duration([double]$Seconds) {
    if ([double]::IsNaN($Seconds) -or [double]::IsInfinity($Seconds) -or $Seconds -lt 0) { return "--:--:--" }
    $span = [TimeSpan]::FromSeconds([Math]::Max(0, $Seconds))
    if ($span.TotalDays -ge 1) {
        return ("{0}d {1:00}:{2:00}:{3:00}" -f [Math]::Floor($span.TotalDays), $span.Hours, $span.Minutes, $span.Seconds)
    }
    return ("{0:00}:{1:00}:{2:00}" -f [Math]::Floor($span.TotalHours), $span.Minutes, $span.Seconds)
}

function Render-Bar([double]$Percent, [int]$Width = 42) {
    $bounded = [Math]::Max(0.0, [Math]::Min(100.0, $Percent))
    $filled = [int][Math]::Floor(($bounded / 100.0) * $Width)
    if ($filled -gt $Width) { $filled = $Width }
    $empty = $Width - $filled
    return "[" + ("#" * $filled) + ("-" * $empty) + "]"
}

$started = [DateTime]::UtcNow
if ($StartedAtUtc) {
    $parsed = [DateTime]::MinValue
    if ([DateTime]::TryParse($StartedAtUtc, [ref]$parsed)) {
        $started = $parsed.ToUniversalTime()
    }
}

$ledger = Join-Path $EvidenceRoot "external_actions.jsonl"
$integrityPath = Join-Path $EvidenceRoot "integrity.json"
$budgetPath = Join-Path $EvidenceRoot "budget.json"
$lastCount = 0
$lastSample = $started
$emaRate = 0.0

while ($true) {
    $now = [DateTime]::UtcNow
    $calls = Get-LineCount $ledger
    $elapsedSeconds = [Math]::Max(0.001, ($now - $started).TotalSeconds)

    $sampleSeconds = [Math]::Max(0.001, ($now - $lastSample).TotalSeconds)
    $delta = $calls - $lastCount
    if ($delta -gt 0) {
        $instantRate = $delta / $sampleSeconds
        if ($emaRate -le 0) { $emaRate = $instantRate }
        else { $emaRate = (0.25 * $instantRate) + (0.75 * $emaRate) }
        $lastCount = $calls
        $lastSample = $now
    }

    $averageRate = if ($calls -gt 0) { $calls / $elapsedSeconds } else { 0.0 }
    $rate = if ($emaRate -gt 0) { $emaRate } else { $averageRate }
    $remaining = [Math]::Max(0, $TotalActions - $calls)
    $etaSeconds = if ($rate -gt 0) { $remaining / $rate } else { [double]::NaN }
    $etaClock = if ($rate -gt 0) { $now.AddSeconds($etaSeconds).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss") } else { "calculating..." }
    $percent = if ($TotalActions -gt 0) { [Math]::Min(100.0, 100.0 * $calls / $TotalActions) } else { 0.0 }
    $basePercent = if ($BaseActions -gt 0) { [Math]::Min(100.0, 100.0 * $calls / $BaseActions) } else { 0.0 }
    $phase = if ($calls -lt $BaseActions) { "BASE MATRIX" } elseif ($calls -lt $TotalActions) { "DIAGNOSTICS / REPAIR" } else { "CAP REACHED" }

    $done = $false
    $integrityStatus = "running"
    $finalUsed = $null
    if (Test-Path $integrityPath) {
        try {
            $integrity = Get-Content $integrityPath -Raw | ConvertFrom-Json
            $integrityStatus = [string]$integrity.status
            if ($integrityStatus -eq "OK") { $done = $true }
        } catch { $integrityStatus = "unreadable" }
    }
    if (Test-Path $budgetPath) {
        try { $finalUsed = (Get-Content $budgetPath -Raw | ConvertFrom-Json).used } catch { }
    }

    Clear-Host
    Write-Host "INVERTED — HARVEST A LIVE" -ForegroundColor Cyan
    Write-Host "Run: $RunId" -ForegroundColor DarkGray
    Write-Host "Phase: $phase" -ForegroundColor Yellow
    Write-Host ""
    Write-Host ((Render-Bar $percent) + ("  {0,6:N2}%" -f $percent)) -ForegroundColor Green
    Write-Host ""
    Write-Host ("Calls:        {0} / {1} max" -f $calls, $TotalActions)
    Write-Host ("Base matrix:  {0:N2}% of {1}" -f $basePercent, $BaseActions)
    Write-Host ("Elapsed:      {0}" -f (Format-Duration $elapsedSeconds))
    Write-Host ("Rate:         {0:N3} calls/sec  ({1:N2} calls/min)" -f $rate, ($rate * 60.0))
    Write-Host ("Time left*:   {0}" -f (Format-Duration $etaSeconds))
    Write-Host ("ETA*:         {0}" -f $etaClock)
    Write-Host ("Integrity:    {0}" -f $integrityStatus)
    Write-Host ""
    Write-Host "* ETA/progress use the 1,200-action worst-case ceiling; the run may finish earlier." -ForegroundColor DarkGray
    Write-Host "  This pane is read-only and creates zero model/API calls." -ForegroundColor DarkGray

    if ($done) {
        Write-Host ""
        Write-Host "HARVEST A COMPLETE" -ForegroundColor Green
        if ($null -ne $finalUsed) { Write-Host ("Final calls: {0} / {1}" -f $finalUsed, $TotalActions) }
        Write-Host ("Total time:  {0}" -f (Format-Duration $elapsedSeconds))
        break
    }

    if ((Test-Path $StopSignal) -and -not $done) {
        Write-Host ""
        Write-Host "Run process ended; waiting for final evidence/integrity..." -ForegroundColor Yellow
    }

    Start-Sleep -Seconds $RefreshSeconds
}
