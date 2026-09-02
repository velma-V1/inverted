param(
    [string[]]$Models,
    [switch]$SkipRepoTests,
    [switch]$ThenHarvestB
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedBranch = "build/black-magic-evidence-tests"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Fail([string]$Message) {
    Write-Host "HARVEST A SETUP FAILED: $Message" -ForegroundColor Red
    exit 1
}

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "Required command '$Name' was not found in PATH."
    }
}

function Quote-PowerShellSingle([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

$NativeHelper = Join-Path $RepoRoot "scripts\invoke-black-magic-native.ps1"
if (-not (Test-Path $NativeHelper)) { Fail "Missing native process capture helper: $NativeHelper" }
. $NativeHelper

$ChainGates = Join-Path $RepoRoot "scripts\black-magic-chain-gates.ps1"
if (-not (Test-Path $ChainGates)) { Fail "Missing fail-closed chain gate helper: $ChainGates" }
. $ChainGates

Write-Host "=== INVERTED HARVEST A - REAL RUN LAUNCHER ===" -ForegroundColor Cyan

Require-Command git
Require-Command ollama

if (-not (Test-Path ".git")) {
    Fail "Run this script from the inverted repository checkout."
}

$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { Fail "git status failed." }
if ($dirty.Count -gt 0) {
    Fail "Repository has local changes. Commit/stash them before a real evidence run."
}

$currentBranch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { Fail "Could not determine current Git branch." }
if ($currentBranch -ne $ExpectedBranch) {
    Write-Host "Switching to $ExpectedBranch ..."
    git fetch origin $ExpectedBranch
    if ($LASTEXITCODE -ne 0) { Fail "git fetch failed." }
    git switch $ExpectedBranch
    if ($LASTEXITCODE -ne 0) { Fail "git switch failed." }
}

git pull --ff-only origin $ExpectedBranch
if ($LASTEXITCODE -ne 0) { Fail "git pull --ff-only failed." }

$HeadSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { Fail "Could not read repository SHA." }
Write-Host "Code SHA: $HeadSha" -ForegroundColor DarkGray

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python virtual environment ..."
    $created = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -m venv .venv
        if ($LASTEXITCODE -eq 0) { $created = $true }
    }
    if (-not $created -and (Get-Command python -ErrorAction SilentlyContinue)) {
        & python -m venv .venv
        if ($LASTEXITCODE -eq 0) { $created = $true }
    }
    if (-not $created -or -not (Test-Path $VenvPython)) {
        Fail "Could not create .venv. Python 3.11+ is required."
    }
}

$pythonVersionText = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($LASTEXITCODE -ne 0) { Fail "Virtual-environment Python failed." }
$versionParts = $pythonVersionText.Trim().Split('.')
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 11)) {
    Fail "Python 3.11+ is required; found $pythonVersionText."
}
Write-Host "Python: $pythonVersionText"

Write-Host "Installing/verifying repository dependencies ..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed." }
& $VenvPython -m pip install -e ".[test]"
if ($LASTEXITCODE -ne 0) { Fail "Repository dependency installation failed." }

if (-not $SkipRepoTests) {
    Write-Host "Running full preflight repository tests ..."
    & $VenvPython -m pytest -q tests
    if ($LASTEXITCODE -ne 0) { Fail "Preflight tests failed. Real Harvest A was NOT started." }
}

Write-Host "Checking Ollama ..."
$ollamaLines = @(& ollama list 2>&1)
if ($LASTEXITCODE -ne 0) {
    Fail "Ollama is installed but not responding. Start Ollama and rerun this one command."
}

$modelNames = @(
    $ollamaLines |
        Select-Object -Skip 1 |
        ForEach-Object { (($_.ToString().Trim()) -split '\s+')[0] } |
        Where-Object { $_ -and $_ -ne "NAME" }
)
$modelNames = @($modelNames | Select-Object -Unique)

if ($modelNames.Count -lt 3) {
    Write-Host "Installed Ollama models:" -ForegroundColor Yellow
    $modelNames | ForEach-Object { Write-Host "  $_" }
    Fail "The preregistered real Harvest A requires 3 distinct Ollama models; only $($modelNames.Count) are installed."
}

if (-not $Models -or $Models.Count -eq 0) {
    Write-Host "Installed Ollama models:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $modelNames.Count; $i++) {
        Write-Host ("  [{0}] {1}" -f ($i + 1), $modelNames[$i])
    }
    $raw = Read-Host "Enter THREE model numbers once, separated by commas (example 1,2,3)"
    $parts = @($raw.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($parts.Count -ne 3) { Fail "Exactly three model numbers are required." }
    $chosen = @()
    foreach ($part in $parts) {
        $index = 0
        if (-not [int]::TryParse($part, [ref]$index)) { Fail "Model selection '$part' is not a number." }
        if ($index -lt 1 -or $index -gt $modelNames.Count) { Fail "Model selection '$part' is out of range." }
        $chosen += $modelNames[$index - 1]
    }
    $Models = $chosen
}

$Models = @($Models | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($Models.Count -ne 3) { Fail "Exactly three model names are required." }
if (($Models | Select-Object -Unique).Count -ne 3) { Fail "The three Harvest A models must be distinct." }
foreach ($model in $Models) {
    if ($model -notin $modelNames) { Fail "Ollama model '$model' is not installed." }
}

Write-Host "Selected models:" -ForegroundColor Green
$Models | ForEach-Object { Write-Host "  $_" }

$env:INVERTED_MODEL_1 = $Models[0]
$env:INVERTED_MODEL_2 = $Models[1]
$env:INVERTED_MODEL_3 = $Models[2]

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunId = "harvest-a-real-$Timestamp"
$OutputDir = Join-Path $RepoRoot "runs\black-magic-harvest-a"
$RunDir = Join-Path $OutputDir $RunId
$ObserverRoot = Join-Path $RepoRoot "runs\observers\$RunId"
$StopFile = Join-Path $ObserverRoot "STOP"
$LauncherLog = Join-Path $RunDir "launcher-native.log"
$Config = Join-Path $RepoRoot "configs\black-magic-harvest-a-local.yaml"
$Publisher = Join-Path $RepoRoot "scripts\publish-black-magic-harvest-a.ps1"
$Monitor = Join-Path $RepoRoot "scripts\watch-black-magic-harvest-a.ps1"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
New-Item -ItemType Directory -Force -Path $ObserverRoot | Out-Null
if (Test-Path $StopFile) { Remove-Item $StopFile -Force }

$publisherArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $Publisher,
    "-RepoPath", $RepoRoot,
    "-EvidenceRoot", $RunDir,
    "-StagingRoot", $ObserverRoot,
    "-RunId", $RunId,
    "-CodeSha", $HeadSha,
    "-StopSignal", $StopFile
)
$PublisherProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $publisherArgs -PassThru -WindowStyle Hidden

$monitorArgString = "-NoProfile -ExecutionPolicy Bypass -File " + (Quote-PowerShellSingle $Monitor) +
    " -RunDir " + (Quote-PowerShellSingle $RunDir) +
    " -RunId " + (Quote-PowerShellSingle $RunId) +
    " -StopFile " + (Quote-PowerShellSingle $StopFile) +
    " -TotalCalls 1200"

$MonitorProcess = $null
$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if ($wt) {
    try {
        $MonitorProcess = Start-Process -FilePath $wt.Source -ArgumentList @(
            "split-pane", "-V", "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", $Monitor, "-RunDir", $RunDir, "-RunId", $RunId, "-StopFile", $StopFile, "-TotalCalls", "1200"
        ) -PassThru
        Write-Host "Live progress opened in a Windows Terminal split pane." -ForegroundColor Cyan
    }
    catch {
        $MonitorProcess = $null
    }
}
if (-not $MonitorProcess) {
    $MonitorProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", $Monitor, "-RunDir", $RunDir, "-RunId", $RunId, "-StopFile", $StopFile, "-TotalCalls", "1200"
    ) -PassThru
    Write-Host "Live progress opened in a separate PowerShell window." -ForegroundColor Cyan
}

Write-Host "Run ID: $RunId" -ForegroundColor Cyan
Write-Host "Evidence directory: $RunDir"
Write-Host "Remote checkpoint branch: evidence/harvest-a-$RunId" -ForegroundColor Cyan
Write-Host "Starting foreground run. Keep the main terminal open." -ForegroundColor Yellow

$cliArgs = @(
    "-m", "inverted.black_magic.cli",
    "--config", $Config,
    "--output-dir", $OutputDir,
    "--run-id", $RunId
)

$exitCode = 1
try {
    $exitCode = Invoke-BlackMagicNative -Executable $VenvPython -ArgumentList $cliArgs -LogPath $LauncherLog
}
catch {
    $failureText = $_ | Out-String
    Write-Host $failureText -ForegroundColor Red
    Add-Content -Path $LauncherLog -Value $failureText -Encoding UTF8
    $exitCode = 1
}
finally {
    Set-Content -Path $StopFile -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding ASCII
    try {
        if ($PublisherProcess -and -not $PublisherProcess.HasExited) {
            Wait-Process -Id $PublisherProcess.Id -Timeout 45 -ErrorAction SilentlyContinue
        }
    }
    catch { }
}

if ($exitCode -ne 0) {
    Write-Host "HARVEST A RUN FAILED (exit $exitCode). Full native output is saved in:" -ForegroundColor Red
    Write-Host "  $LauncherLog" -ForegroundColor Red
    Write-Host "The failure log and partial evidence are also published to the evidence branch when GitHub is reachable." -ForegroundColor Yellow
    exit $exitCode
}

try {
    Assert-HarvestCompletionPacket -EvidenceDir $RunDir -Label "Harvest A" | Out-Null
}
catch {
    Write-Host "HARVEST A EVIDENCE GATE FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "HARVEST A RUN COMPLETE." -ForegroundColor Green
Write-Host "Local evidence: $RunDir"
Write-Host "Remote evidence: evidence/harvest-a-$RunId"

if ($ThenHarvestB) {
    Write-Host "Harvest A evidence gate passed. Starting Harvest B automatically." -ForegroundColor Cyan

    $HarvestBTimestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $HarvestBRunId = "harvest-b-real-$HarvestBTimestamp"
    $HarvestBOutputDir = Join-Path $RepoRoot "runs"
    $HarvestBRunDir = Join-Path $HarvestBOutputDir "black-magic\epistemic_harvest\$HarvestBRunId"
    $HarvestBConfig = Join-Path $RepoRoot "configs\black-magic-harvest-b-local.yaml"
    $HarvestBLog = Join-Path $HarvestBRunDir "launcher-native.log"

    New-Item -ItemType Directory -Force -Path $HarvestBRunDir | Out-Null

    Write-Host "Harvest B run ID: $HarvestBRunId" -ForegroundColor Cyan
    Write-Host "Harvest B evidence directory: $HarvestBRunDir"

    $harvestBArgs = @(
        "-m", "inverted.black_magic.epistemic_cli",
        "--config", $HarvestBConfig,
        "--output-dir", $HarvestBOutputDir,
        "--run-id", $HarvestBRunId
    )

    $harvestBExit = 1
    try {
        $harvestBExit = Invoke-BlackMagicNative -Executable $VenvPython -ArgumentList $harvestBArgs -LogPath $HarvestBLog
    }
    catch {
        $failureText = $_ | Out-String
        Write-Host $failureText -ForegroundColor Red
        Add-Content -Path $HarvestBLog -Value $failureText -Encoding UTF8
        $harvestBExit = 1
    }

    if ($harvestBExit -ne 0) {
        Write-Host "HARVEST B RUN FAILED (exit $harvestBExit). Full native output is saved in:" -ForegroundColor Red
        Write-Host "  $HarvestBLog" -ForegroundColor Red
        exit $harvestBExit
    }

    try {
        Assert-HarvestCompletionPacket -EvidenceDir $HarvestBRunDir -Label "Harvest B" | Out-Null
    }
    catch {
        Write-Host "HARVEST B EVIDENCE GATE FAILED: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }

    Write-Host "HARVEST B RUN COMPLETE." -ForegroundColor Green
    Write-Host "Harvest B evidence: $HarvestBRunDir"
}
