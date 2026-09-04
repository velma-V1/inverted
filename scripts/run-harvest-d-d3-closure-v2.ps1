param(
    [string]$Config = "configs/harvest-d-d3-closure-v2.json",
    [string]$Output = "runs/harvest-d-d3-closure-v2",
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
    "tests/test_harvest_d_d4_qwen_policy.py",
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

Write-Host "D3-Closure v2 real local campaign"
if ($MaxCalls -gt 0) {
    python -m inverted.harvest_d.d3_closure_cli --config $Config --output $Output --max-calls $MaxCalls
} else {
    python -m inverted.harvest_d.d3_closure_cli --config $Config --output $Output
}
if ($LASTEXITCODE -ne 0) {
    throw "D3-Closure campaign halted or failed. Inspect the evidence package; no automatic retry is permitted."
}

Write-Host "D3-Closure v2 campaign completed without a harness hard stop."
