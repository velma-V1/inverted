param(
    [string]$ProcessPattern = "alien",
    [string]$RepoPath = "$HOME\inverted",
    [string]$PythonExe = "C:\Python314\python.exe",
    [string]$Model1 = "qwen3.5:9b-q8_0",
    [string]$Model2 = "gemma3:12b",
    [string]$Model3 = "devstral-small-2:24b",
    [string]$RunRoot = "$HOME\inverted-runs"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " HANDOFF STOPPED" -ForegroundColor Red
    Write-Host " $Message" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    throw $Message
}

function Get-010Processes {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(\.exe)?$' -and
        $_.CommandLine -and
        $_.CommandLine -match $ProcessPattern
    })
}

New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$StateFile = Join-Path $RunRoot "active-run-id.txt"
$ResumeExisting = Test-Path $StateFile

# Keep the computer awake while plugged in. Display timeout is unaffected.
powercfg /change standby-timeout-ac 0

if (-not $ResumeExisting) {
    Write-Host "============================================================"
    Write-Host " WAITING FOR 010 LIVE C/D TEST"
    Write-Host " Process pattern: $ProcessPattern"
    Write-Host "============================================================"

    $Seen010 = $false
    $ClearChecks = 0
    $WaitStart = Get-Date

    while ($true) {
        $Matches = Get-010Processes
        if ($Matches.Count -gt 0) {
            $Seen010 = $true
            $ClearChecks = 0
            $Elapsed = (Get-Date) - $WaitStart
            $Pids = ($Matches | ForEach-Object { $_.ProcessId }) -join ","
            Write-Progress -Id 1 -Activity "010 LIVE C/D TEST RUNNING" -Status ("Elapsed {0:hh\:mm\:ss} | PID(s): {1}" -f $Elapsed, $Pids)
            Start-Sleep -Seconds 10
            continue
        }

        if (-not $Seen010) {
            Write-Progress -Id 1 -Activity "010 watcher" -Completed
            Fail "No running 010 process matched '$ProcessPattern'; refusing to start the inverted benchmark."
        }

        $ClearChecks++
        Write-Progress -Id 1 -Activity "VERIFYING 010 HAS FINISHED" -Status "No match: confirmation $ClearChecks of 3"
        if ($ClearChecks -ge 3) {
            break
        }
        Start-Sleep -Seconds 10
    }

    Write-Progress -Id 1 -Activity "010 watcher" -Completed
    Write-Host "010 process has remained absent for three consecutive checks."
} else {
    Write-Host "Existing inverted run state found. Resuming run ID: $(Get-Content $StateFile -Raw)"
}

Write-Host ""
Write-Host "============================================================"
Write-Host " PREPARING INVERTED BENCHMARK"
Write-Host "============================================================"

if (-not (Test-Path $PythonExe)) {
    Fail "Python executable not found: $PythonExe"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "git is not available on PATH."
}

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    Write-Host "Cloning velma-V1/inverted..."
    & git clone "https://github.com/velma-V1/inverted.git" $RepoPath
    if ($LASTEXITCODE -ne 0) { Fail "git clone failed with exit code $LASTEXITCODE" }
}

& git -C $RepoPath checkout main
if ($LASTEXITCODE -ne 0) { Fail "git checkout main failed with exit code $LASTEXITCODE" }
& git -C $RepoPath pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { Fail "git pull failed with exit code $LASTEXITCODE" }

$ConfigPath = Join-Path $RepoPath "configs\decisive.yaml"
$CliPath = Join-Path $RepoPath "src\inverted\cli.py"
if (-not (Test-Path $ConfigPath)) { Fail "Missing decisive config: $ConfigPath" }
if (-not (Test-Path $CliPath)) { Fail "Missing benchmark package: $CliPath" }

Write-Host "Installing/verifying benchmark package..."
& $PythonExe -m pip install -e $RepoPath
if ($LASTEXITCODE -ne 0) { Fail "Benchmark installation failed with exit code $LASTEXITCODE" }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Fail "Ollama is not available on PATH."
}

Write-Host "Checking Ollama models..."
$OllamaList = (& ollama list 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { Fail "ollama list failed with exit code $LASTEXITCODE" }

$RequiredModels = @($Model1, $Model2, $Model3)
foreach ($Model in $RequiredModels) {
    if ($OllamaList -notmatch [regex]::Escape($Model)) {
        Fail "Required Ollama model missing: $Model"
    }
    Write-Host "  OK: $Model"
}

$env:INVERTED_MODEL_1 = $Model1
$env:INVERTED_MODEL_2 = $Model2
$env:INVERTED_MODEL_3 = $Model3

if ($ResumeExisting) {
    $RunId = (Get-Content $StateFile -Raw).Trim()
    if (-not $RunId) { Fail "Existing active-run-id.txt is empty." }
} else {
    $RunId = "decisive-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Set-Content -Path $StateFile -Value $RunId -Encoding UTF8
}

$Checkpoint = Join-Path $RunRoot "$RunId.checkpoint.jsonl"
$TerminalLog = Join-Path $RunRoot "$RunId-terminal.log"
$RunDir = Join-Path $RunRoot $RunId

Write-Host ""
Write-Host "============================================================"
Write-Host " STARTING REAL-MODEL INVERTED BENCHMARK"
Write-Host " Run ID: $RunId"
Write-Host " Model 1: $Model1"
Write-Host " Model 2: $Model2"
Write-Host " Model 3: $Model3"
Write-Host " Checkpoint: $Checkpoint"
Write-Host "============================================================"

$Start = Get-Date
& $PythonExe -m inverted.cli `
    --config $ConfigPath `
    --output-dir $RunRoot `
    --run-id $RunId `
    --checkpoint $Checkpoint `
    --resume `
    --progress 2>&1 | Tee-Object -FilePath $TerminalLog
$BenchmarkExitCode = $LASTEXITCODE

if ($BenchmarkExitCode -ne 0) {
    Fail "Inverted benchmark failed with exit code $BenchmarkExitCode. Run state and checkpoint were preserved for resume."
}

$RequiredArtifacts = @(
    "events.jsonl",
    "model_calls.jsonl",
    "trials.csv",
    "trials.jsonl",
    "failures.csv",
    "summary.json",
    "summary.csv",
    "report.txt",
    "config.json",
    "provenance.json"
)

foreach ($Artifact in $RequiredArtifacts) {
    $ArtifactPath = Join-Path $RunDir $Artifact
    if (-not (Test-Path $ArtifactPath)) {
        Fail "Benchmark exited successfully but required artifact is missing: $ArtifactPath"
    }
}

$Elapsed = (Get-Date) - $Start
Remove-Item $StateFile -Force

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " INVERTED BENCHMARK COMPLETE" -ForegroundColor Green
Write-Host (" Runtime: {0:hh\:mm\:ss}" -f $Elapsed)
Write-Host " Results: $RunDir"
Write-Host " Terminal log: $TerminalLog"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press ENTER to close"
