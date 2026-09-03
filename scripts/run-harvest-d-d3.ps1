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
python -m pytest -q tests/test_harvest_d_d3_*.py tests/test_progress_display.py tests/test_campaign_progress_policy.py
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
