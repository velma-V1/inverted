param(
    [string]$Config = "configs/harvest-d-d3.json",
    [string]$Output = "runs/harvest-d-d3",
    [switch]$ModelFreeOnly,
    [int]$MaxCalls = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$GateOutput = "$Output-model-free-gate"
if (Test-Path $GateOutput) {
    Remove-Item -Recurse -Force $GateOutput
}

Write-Host "D3 gate: focused model-free tests"
$D3Tests = @(
    Get-ChildItem -Path "tests" -Filter "test_harvest_d_d3_*.py" -File |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
)
if ($D3Tests.Count -eq 0) {
    throw "No D3 focused tests were found; no model calls were started."
}
$ValidationTests = @($D3Tests) + @(
    "tests/test_progress_display.py",
    "tests/test_campaign_progress_policy.py"
)
python -m pytest -q @ValidationTests
if ($LASTEXITCODE -ne 0) {
    throw "D3 focused validation failed; no model calls were started."
}

Write-Host "D3 gate: zero-call model-free campaign"
python -m inverted.harvest_d.d3_cli --config $Config --output $GateOutput --model-free
if ($LASTEXITCODE -ne 0) {
    throw "D3 model-free preflight failed; no model calls were started."
}

if ($ModelFreeOnly) {
    Write-Host "D3 model-free gate complete."
    exit 0
}

Write-Host "D3 real local campaign"
if ($MaxCalls -gt 0) {
    python -m inverted.harvest_d.d3_cli --config $Config --output $Output --max-calls $MaxCalls
} else {
    python -m inverted.harvest_d.d3_cli --config $Config --output $Output
}
if ($LASTEXITCODE -ne 0) {
    throw "D3 campaign halted or failed. Inspect the evidence package before any further inference."
}

Write-Host "D3 campaign completed without a harness hard stop."
