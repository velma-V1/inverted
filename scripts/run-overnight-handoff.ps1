param(
    [string]$RepoPath = "$HOME\inverted",
    [string]$RunRoot = "$HOME\inverted-runs",
    [string]$PythonExe = "C:\Python314\python.exe",
    [string]$Model1 = "qwen3.5:9b-q8_0",
    [string]$Model2 = "llama3.1:8b",
    [string]$Model3 = "phi4-mini:3.8b"
)

$ErrorActionPreference = "Stop"
$Watcher = Join-Path $RepoPath "scripts\wait-for-010-and-run-inverted.ps1"
$Publisher = Join-Path $RepoPath "scripts\publish-inverted-checkpoints.ps1"
$StateFile = Join-Path $RunRoot "active-run-id.txt"
$StopSignal = Join-Path $RunRoot "publisher-wrapper-stop.signal"
$TerminalLog = $null

if (-not (Test-Path $Watcher)) { throw "Missing handoff watcher: $Watcher" }
if (-not (Test-Path $Publisher)) { throw "Missing checkpoint publisher: $Publisher" }
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
Remove-Item $StopSignal -Force -ErrorAction SilentlyContinue

Write-Host "============================================================"
Write-Host " OVERNIGHT HANDOFF ARMED"
Write-Host " 010 -> publish 010 -> inverted -> GitHub checkpoints"
Write-Host "============================================================"

$PublisherJob = Start-Job -Name "INVERTED_CHECKPOINT_PUBLISHER" -ScriptBlock {
    param($RepoPath, $RunRoot, $StateFile, $StopSignal, $Publisher)

    while (-not (Test-Path $StateFile)) {
        if (Test-Path $StopSignal) { return }
        Start-Sleep -Seconds 2
    }

    $RunId = (Get-Content $StateFile -Raw).Trim()
    if (-not $RunId) { return }
    $Checkpoint = Join-Path $RunRoot "$RunId.checkpoint.jsonl"
    $FinalRunDir = Join-Path $RunRoot $RunId

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Publisher `
        -RepoPath $RepoPath `
        -RunRoot $RunRoot `
        -RunId $RunId `
        -Checkpoint $Checkpoint `
        -StopSignal $StopSignal `
        -FinalRunDir $FinalRunDir
} -ArgumentList $RepoPath, $RunRoot, $StateFile, $StopSignal, $Publisher

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Watcher `
        -RepoPath $RepoPath `
        -RunRoot $RunRoot `
        -PythonExe $PythonExe `
        -Model1 $Model1 `
        -Model2 $Model2 `
        -Model3 $Model3
    $WatcherExit = $LASTEXITCODE

    if (Test-Path $StateFile) {
        $RunId = (Get-Content $StateFile -Raw).Trim()
        if ($RunId) { $TerminalLog = Join-Path $RunRoot "$RunId-terminal.log" }
    }
} finally {
    New-Item -ItemType File -Force -Path $StopSignal | Out-Null
    Write-Host ""
    Write-Host "Flushing final GitHub checkpoint publication..."
    Wait-Job $PublisherJob -Timeout 120 | Out-Null
    Receive-Job $PublisherJob -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    Remove-Job $PublisherJob -Force -ErrorAction SilentlyContinue
    Remove-Item $StopSignal -Force -ErrorAction SilentlyContinue
}

if ($WatcherExit -ne 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " ROOT FAILURE FROM TERMINAL LOG" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    if ($TerminalLog -and (Test-Path $TerminalLog)) {
        Get-Content -Path $TerminalLog -Tail 80 | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "Terminal log unavailable. Watcher exit code: $WatcherExit" -ForegroundColor Red
    }
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "Run state/checkpoint preserved. Watcher exit code: $WatcherExit" -ForegroundColor Red
    exit $WatcherExit
}
