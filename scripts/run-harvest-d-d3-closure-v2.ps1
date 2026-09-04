param(
    [string]$Config = "configs/harvest-d-d3-closure-v2.json",
    [string]$Output = "runs/harvest-d-d3-closure-v2",
    [string]$D4Output = "runs/harvest-d-d4-qwen-policy",
    [string]$D3V1Input = "runs/harvest-d-d3",
    [string]$PostD3Output = "runs/post-d3-analysis",
    [switch]$ModelFreeOnly,
    [int]$MaxCalls = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$GateOutput = "$Output-model-free-gate"
if (Test-Path $GateOutput) {
    Remove-Item -Recurse -Force $GateOutput
}

Write-Host "D3-Closure v2 gate: focused model-free tests"
$ClosureTests = @(
    Get-ChildItem -Path "tests" -Filter "test_harvest_d_d3_closure_*.py" -File |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
)
if ($ClosureTests.Count -eq 0) {
    throw "No D3-Closure focused tests were found; no model calls were started."
}
$ValidationTests = @($ClosureTests) + @(
    (Get-ChildItem -Path "tests" -Filter "test_harvest_d_d4_qwen_*.py" -File | Sort-Object Name | ForEach-Object { $_.FullName }),
    "tests/test_harvest_d_post_d3_analysis.py",
    "tests/test_progress_display.py",
    "tests/test_campaign_progress_policy.py"
)
python -m pytest -q @ValidationTests
if ($LASTEXITCODE -ne 0) {
    throw "D3-Closure focused validation failed; no model calls were started."
}

Write-Host "D3-Closure v2 gate: zero-call model-free package"
python -m inverted.harvest_d.d3_closure_cli --config $Config --output $GateOutput --model-free
if ($LASTEXITCODE -ne 0) {
    throw "D3-Closure model-free preflight failed; no model calls were started."
}

if ($ModelFreeOnly) {
    Write-Host "D3-Closure v2 model-free gate complete."
    exit 0
}

$GapRegistry = Join-Path $PostD3Output "post_d3_gap_registry.json"
if (-not (Test-Path $GapRegistry)) {
    if (-not (Test-Path $D3V1Input)) {
        throw "Frozen D3-v1 evidence is unavailable and post-D3 analysis is missing; no model calls were started."
    }
    Write-Host "D3-Closure prerequisite: zero-call post-D3 analysis"
    python -m inverted.harvest_d.post_d3_cli --input $D3V1Input --output $PostD3Output
    if ($LASTEXITCODE -ne 0) {
        throw "Post-D3 zero-call analysis failed; no model calls were started."
    }
}
if (-not (Test-Path $GapRegistry)) {
    throw "Required post-D3 gap registry was not produced; no model calls were started."
}

$D4PolicyFile = Join-Path $D4Output "d4_frozen_policy.json"
$D4Frozen = $false
if (Test-Path $D4PolicyFile) {
    try {
        $ExistingD4 = Get-Content $D4PolicyFile -Raw | ConvertFrom-Json
        $D4Frozen = ($ExistingD4.state -eq "FROZEN")
    } catch {
        $D4Frozen = $false
    }
}
if (-not $D4Frozen) {
    Write-Host "D3-Closure prerequisite: D4 Qwen call-policy gate"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-harvest-d-d4-qwen-policy.ps1 -Output $D4Output -D3V1Input $D3V1Input -PostD3Output $PostD3Output
    if ($LASTEXITCODE -ne 0) {
        throw "D4 Qwen policy gate failed or remained unresolved; D3-Closure model calls were not started."
    }
}
if (-not (Test-Path $D4PolicyFile)) {
    throw "D4 frozen policy artifact is missing; D3-Closure model calls were not started."
}
$FinalD4 = Get-Content $D4PolicyFile -Raw | ConvertFrom-Json
if ($FinalD4.state -ne "FROZEN") {
    throw "D4 policy is not frozen; D3-Closure model calls were not started."
}

Write-Host "D3-Closure v2 real local campaign"
if ($MaxCalls -gt 0) {
    python -m inverted.harvest_d.d3_closure_cli --config $Config --output $Output --d4-policy-file $D4PolicyFile --max-calls $MaxCalls
} else {
    python -m inverted.harvest_d.d3_closure_cli --config $Config --output $Output --d4-policy-file $D4PolicyFile
}
if ($LASTEXITCODE -ne 0) {
    throw "D3-Closure campaign halted or failed. Inspect the evidence package; no automatic retry is permitted."
}

Write-Host "D3-Closure v2 campaign completed without a harness hard stop."
