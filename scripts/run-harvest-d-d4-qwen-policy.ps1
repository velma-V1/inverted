param(
    [string]$Config = "configs/harvest-d-d4-qwen-policy.json",
    [string]$Output = "runs/harvest-d-d4-qwen-policy",
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

Write-Host "D4 Qwen policy gate: focused model-free tests"
$D4Tests = @(
    Get-ChildItem -Path "tests" -Filter "test_harvest_d_d4_qwen_*.py" -File |
        Sort-Object Name |
        ForEach-Object { $_.FullName }
)
if ($D4Tests.Count -eq 0) {
    throw "No D4 focused tests were found; no model calls were started."
}
$ValidationTests = @($D4Tests) + @(
    "tests/test_harvest_d_post_d3_analysis.py",
    "tests/test_progress_display.py",
    "tests/test_campaign_progress_policy.py"
)
python -m pytest -q @ValidationTests
if ($LASTEXITCODE -ne 0) {
    throw "D4 focused validation failed; no model calls were started."
}

Write-Host "D4 Qwen policy gate: zero-call model-free package"
python -m inverted.harvest_d.d4_qwen_cli --config $Config --output $GateOutput --model-free
if ($LASTEXITCODE -ne 0) {
    throw "D4 model-free preflight failed; no model calls were started."
}

if ($ModelFreeOnly) {
    Write-Host "D4 Qwen policy model-free gate complete."
    exit 0
}

$GapRegistry = Join-Path $PostD3Output "post_d3_gap_registry.json"
if (!(Test-Path -LiteralPath $D3V1Input)) {
    throw "Frozen D3-v1 evidence is unavailable; no model calls were started."
}
Write-Host "D4 prerequisite: revalidate frozen D3-v1 and rebuild zero-call post-D3 analysis"
python -m inverted.harvest_d.post_d3_cli --input $D3V1Input --output $PostD3Output
if ($LASTEXITCODE -ne 0) {
    throw "Post-D3 zero-call analysis/revalidation failed; no model calls were started."
}
if (!(Test-Path -LiteralPath $GapRegistry)) {
    throw "Required post-D3 gap registry was not produced; no model calls were started."
}

Write-Host "D4 Qwen policy real local campaign"
if ($MaxCalls -gt 0) {
    python -m inverted.harvest_d.d4_qwen_cli --config $Config --output $Output --max-calls $MaxCalls
} else {
    python -m inverted.harvest_d.d4_qwen_cli --config $Config --output $Output
}
if ($LASTEXITCODE -ne 0) {
    throw "D4 Qwen policy did not freeze a valid policy. Inspect D4 evidence; no automatic retry is permitted."
}

Write-Host "D4 Qwen policy completed with a frozen policy."
