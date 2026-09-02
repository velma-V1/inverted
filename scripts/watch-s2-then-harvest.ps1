param(
    [string]$RepoPath = (Split-Path $PSScriptRoot -Parent),
    [string]$GateScript,
    [string]$S2EvidenceDir = "test3-s2-results\tier-a",
    [string]$S2RunId = "tier-a-real",
    [string[]]$Models = @(
        "ministral-3:3b-instruct-2512-q8_0",
        "qwen3.5:9b-q8_0",
        "devstral-small-2:24b"
    ),
    [int]$ExpectedS2ModelCalls = 720,
    [int]$PollSeconds = 10,
    [switch]$AllowAlreadyComplete
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$TargetBranch = "build/black-magic-evidence-tests"
$RepoRoot = [System.IO.Path]::GetFullPath($RepoPath)
Set-Location $RepoRoot

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    throw "S2 handoff requires the inverted repository checkout: $RepoRoot"
}
if ($PollSeconds -lt 1) { throw "PollSeconds must be at least 1" }
if ($Models.Count -ne 3 -or ($Models | Select-Object -Unique).Count -ne 3) {
    throw "The S2-to-Harvest chain requires exactly three distinct Harvest models"
}

$S2EvidencePath = if ([System.IO.Path]::IsPathRooted($S2EvidenceDir)) {
    [System.IO.Path]::GetFullPath($S2EvidenceDir)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $S2EvidenceDir))
}

if (-not $GateScript) {
    $candidate = Join-Path $PSScriptRoot "black-magic-chain-gates.ps1"
    if (Test-Path $candidate) { $GateScript = $candidate }
}
if (-not $GateScript -or -not (Test-Path $GateScript)) {
    throw "Missing fail-closed gate script. Pass -GateScript with black-magic-chain-gates.ps1"
}
. ([System.IO.Path]::GetFullPath($GateScript))

function Get-S2Processes {
    $rows = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $line = [string]$_.CommandLine
        $line -match 'inverted\.test3_s2_cli' -and $line -match [regex]::Escape($S2RunId)
    })
    return $rows
}

function WaitForS2 {
    $initial = @(Get-S2Processes)
    if ($initial.Count -eq 0) {
        if ($AllowAlreadyComplete) {
            Assert-S2CompletionPacket -EvidenceDir $S2EvidencePath -RunId $S2RunId -ExpectedModelCalls $ExpectedS2ModelCalls | Out-Null
            Write-Host "S2 packet was already complete and passed the handoff gate." -ForegroundColor Green
            return
        }
        throw "No active S2 process for run '$S2RunId' was found. Chain not armed."
    }

    Write-Host "S2 -> Harvest A -> Harvest B chain ARMED." -ForegroundColor Cyan
    Write-Host "Waiting for S2 run '$S2RunId' to exit before validating evidence..." -ForegroundColor Cyan
    while ($true) {
        $active = @(Get-S2Processes)
        if ($active.Count -eq 0) { break }
        Start-Sleep -Seconds $PollSeconds
    }

    Assert-S2CompletionPacket -EvidenceDir $S2EvidencePath -RunId $S2RunId -ExpectedModelCalls $ExpectedS2ModelCalls | Out-Null
    Write-Host "S2 COMPLETE evidence gate passed: $ExpectedS2ModelCalls model calls." -ForegroundColor Green
}

WaitForS2

& git -C $RepoRoot diff --quiet --ignore-submodules --
$trackedWorktreeExit = $LASTEXITCODE
if ($trackedWorktreeExit -ne 0) {
    throw "Tracked working-tree changes exist after S2. Refusing automatic branch handoff."
}
& git -C $RepoRoot diff --cached --quiet --ignore-submodules --
$trackedIndexExit = $LASTEXITCODE
if ($trackedIndexExit -ne 0) {
    throw "Staged tracked changes exist after S2. Refusing automatic branch handoff."
}

Write-Host "Switching to $TargetBranch for Harvest A/B..." -ForegroundColor Cyan
& git -C $RepoRoot fetch origin $TargetBranch
if ($LASTEXITCODE -ne 0) { throw "git fetch failed during S2 handoff" }
& git -C $RepoRoot switch $TargetBranch
if ($LASTEXITCODE -ne 0) { throw "git switch failed during S2 handoff" }
& git -C $RepoRoot pull --ff-only origin $TargetBranch
if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only failed during S2 handoff" }

$Launcher = Join-Path $RepoRoot "run-harvest-a.ps1"
if (-not (Test-Path $Launcher)) { throw "Harvest A launcher missing after branch handoff: $Launcher" }

Write-Host "Starting Harvest A. Harvest B is chained behind its completion gate." -ForegroundColor Green
& $Launcher -Models $Models -ThenHarvestB
