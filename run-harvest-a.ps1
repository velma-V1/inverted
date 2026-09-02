param(
    [string[]]$Models,
    [string]$RunId,
    [string]$OutputDir = "runs",
    [switch]$SkipRepoTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedBranch = "build/black-magic-evidence-tests"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Fail([string]$Message) {
    Write-Host "`nHARVEST A SETUP FAILED: $Message" -ForegroundColor Red
    exit 1
}

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "Required command '$Name' was not found."
    }
}

Write-Host "=== INVERTED HARVEST A — REAL RUN LAUNCHER ===" -ForegroundColor Cyan

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
    & $VenvPython -m pytest -q
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

if ($Models -and $Models.Count -gt 0) {
    if ($Models.Count -ne 3) { Fail "-Models must contain exactly 3 model names." }
    $selected = @($Models)
} elseif ($env:INVERTED_MODEL_1 -and $env:INVERTED_MODEL_2 -and $env:INVERTED_MODEL_3) {
    $selected = @($env:INVERTED_MODEL_1, $env:INVERTED_MODEL_2, $env:INVERTED_MODEL_3)
    Write-Host "Using existing INVERTED_MODEL_1/2/3 environment variables."
} elseif ($modelNames.Count -eq 3) {
    $selected = @($modelNames)
    Write-Host "Exactly 3 Ollama models found; selecting them automatically."
} else {
    Write-Host "`nInstalled Ollama models:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $modelNames.Count; $i++) {
        Write-Host "  [$($i + 1)] $($modelNames[$i])"
    }
    $answer = Read-Host "Enter THREE model numbers once, separated by commas (example 1,2,3)"
    $indexes = @($answer -split ',' | ForEach-Object { $_.Trim() })
    if ($indexes.Count -ne 3) { Fail "Exactly three model numbers are required." }
    $chosenIndexes = New-Object System.Collections.Generic.List[int]
    foreach ($item in $indexes) {
        $number = 0
        if (-not [int]::TryParse($item, [ref]$number)) { Fail "'$item' is not a valid model number." }
        if ($number -lt 1 -or $number -gt $modelNames.Count) { Fail "Model number $number is out of range." }
        $chosenIndexes.Add($number - 1)
    }
    $selected = @($chosenIndexes | ForEach-Object { $modelNames[$_] })
}

if ((@($selected | Select-Object -Unique)).Count -ne 3) {
    Fail "Harvest A requires 3 distinct models. Duplicate model selections are not allowed."
}
foreach ($model in $selected) {
    if ($modelNames -notcontains $model) {
        Fail "Selected model '$model' is not installed in Ollama."
    }
}

$env:INVERTED_MODEL_1 = $selected[0]
$env:INVERTED_MODEL_2 = $selected[1]
$env:INVERTED_MODEL_3 = $selected[2]

Write-Host "`nHarvest A models:" -ForegroundColor Green
Write-Host "  1: $($selected[0])"
Write-Host "  2: $($selected[1])"
Write-Host "  3: $($selected[2])"

if (-not $RunId) {
    $RunId = "harvest-a-real-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

$Config = "configs/black-magic-harvest-a-local.yaml"
if (-not (Test-Path $Config)) { Fail "Missing $Config." }

$LogDir = Join-Path $RepoRoot "$OutputDir\launcher-logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir "$RunId.txt"

Write-Host "`nREAL HARVEST A" -ForegroundColor Magenta
Write-Host "  Run ID: $RunId"
Write-Host "  Hard cap: 1,200 external actions"
Write-Host "  Base matrix: 3 models x 100 cases x 3 arms = 900"
Write-Host "  Diagnostic reserve: up to 300"
Write-Host "  Output dir: $OutputDir"
Write-Host "  Launcher log: $LogPath"
Write-Host "`nStarting foreground run. Do not close this terminal." -ForegroundColor Yellow

$startRecord = [ordered]@{
    run_id = $RunId
    code_sha = $HeadSha
    started_at = (Get-Date).ToString("o")
    model_1 = $selected[0]
    model_2 = $selected[1]
    model_3 = $selected[2]
    config = $Config
}
($startRecord | ConvertTo-Json) | Set-Content -Encoding UTF8 $LogPath

& $VenvPython -m inverted.black_magic.cli `
    --config $Config `
    --stage decision_harvest `
    --output-dir $OutputDir `
    --run-id $RunId 2>&1 | Tee-Object -FilePath $LogPath -Append
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Fail "Harvest A exited with code $exitCode. Evidence/logs were preserved at $OutputDir and $LogPath."
}

$EvidenceRoot = Join-Path $RepoRoot "$OutputDir\black-magic\decision_harvest\$RunId"
if (-not (Test-Path $EvidenceRoot)) {
    Fail "Runner exited successfully but expected evidence root was not found: $EvidenceRoot"
}

$IntegrityPath = Join-Path $EvidenceRoot "integrity.json"
$BudgetPath = Join-Path $EvidenceRoot "budget.json"
if (-not (Test-Path $IntegrityPath) -or -not (Test-Path $BudgetPath)) {
    Fail "Run completed but required integrity/budget artifacts are missing."
}
$integrity = Get-Content $IntegrityPath -Raw | ConvertFrom-Json
$budget = Get-Content $BudgetPath -Raw | ConvertFrom-Json
if ($integrity.status -ne "OK") {
    Fail "Harvest A produced evidence but integrity status is '$($integrity.status)'."
}

Write-Host "`n=== HARVEST A COMPLETE ===" -ForegroundColor Green
Write-Host "Evidence: $EvidenceRoot"
Write-Host "Integrity: $($integrity.status)"
Write-Host "External actions used: $($budget.used) / $($budget.cap)"
Write-Host "Code SHA: $HeadSha"
