param(
    [string]$Config = "configs/harvest-d-d3-closure-v2.json",
    [string]$Output = "runs/harvest-d-d3-closure-r1",
    [string]$R0Output = "runs/harvest-d-d3-closure-r0-gate",
    [string]$D4Output = "runs/harvest-d-d4-qwen-policy",
    [string]$StageAuthorization = "configs/harvest-d-d3-closure-v2-r1-authorization.json",
    [string]$LegacyAuthorization = "configs/harvest-d-d3-closure-v2-execution-authorization.json",
    [switch]$ModelFreeOnly,
    [int]$MaxCalls = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($MaxCalls -gt 24) {
    throw "R1 MaxCalls -gt 24 is forbidden; no model calls were started."
}

Write-Host "R1 prerequisite: fresh zero-call R0 package"
if (Test-Path $R0Output) { Remove-Item -Recurse -Force $R0Output }
python -m inverted.harvest_d.d3_closure_cli --config $Config --output $R0Output --model-free
if ($LASTEXITCODE -ne 0) {
    throw "Fresh R0 model-free gate failed; no R1 model calls were started."
}
$R0Readiness = Join-Path $R0Output "closure_r0_readiness_report.json"
if (-not (Test-Path $R0Readiness)) {
    throw "Fresh R0 readiness report is missing; no R1 model calls were started."
}
$R0 = Get-Content $R0Readiness -Raw | ConvertFrom-Json
if ($R0.final_state -ne "R0_MODEL_FREE_COMPLETE" -or $R0.r0_ready -ne $true) {
    throw "R0_MODEL_FREE_COMPLETE was not achieved; no R1 model calls were started."
}
if ($R0.physical_model_calls -ne 0 -or $R0.physical_execution_authorized -ne $false) {
    throw "R0 evidence state is contaminated or over-authorized; no R1 model calls were started."
}
if ($R0.evidence_tier_integrity -ne $true -or $R0.uncovered_mandatory_obligations -ne 0) {
    throw "R0 evidence-tier or mandatory-obligation gate is not green; no R1 model calls were started."
}

$GateOutput = "$Output-model-free-gate"
if (Test-Path $GateOutput) { Remove-Item -Recurse -Force $GateOutput }
Write-Host "R1 calibration gate: focused tests"
$Tests = @(
    "tests/test_harvest_d_d3_closure_r1.py",
    "tests/test_harvest_d_d3_closure_r1_launcher_windows.py",
    "tests/test_harvest_d_d3_closure_r0.py",
    "tests/test_harvest_d_d3_closure_r0_adequacy.py",
    "tests/test_harvest_d_d3_closure_r0_integration.py"
)
python -m pytest -q @Tests
if ($LASTEXITCODE -ne 0) {
    throw "R1 focused validation failed; no model calls were started."
}

Write-Host "R1 calibration gate: zero-call package"
python -m inverted.harvest_d.d3_closure_r1_cli --config $Config --output $GateOutput --model-free
if ($LASTEXITCODE -ne 0) {
    throw "R1 model-free package failed; no model calls were started."
}

if ($ModelFreeOnly) {
    Write-Host "R1 model-free gate complete."
    exit 0
}

if (-not (Test-Path $StageAuthorization)) {
    throw "R1 StageAuthorization is missing; no model calls were started."
}
$Stage = Get-Content $StageAuthorization -Raw | ConvertFrom-Json
if ($Stage.protocol -ne "D3-CLOSURE-v2" -or $Stage.stage -ne "R1_CALIBRATION") {
    throw "R1 stage authorization identity mismatch; no model calls were started."
}
if ($Stage.stage_physical_execution_authorized -ne $true -or $Stage.max_physical_calls -ne 24) {
    throw "R1 stage_physical_execution_authorized gate is not valid; no model calls were started."
}
if ($Stage.legacy_closure_physical_execution_authorized -ne $false) {
    throw "R1 authorization illegally permits legacy Closure; no model calls were started."
}
if (-not (Test-Path $LegacyAuthorization)) {
    throw "Legacy Closure authorization file is missing; no model calls were started."
}
$Legacy = Get-Content $LegacyAuthorization -Raw | ConvertFrom-Json
if ($Legacy.physical_execution_authorized -ne $false) {
    throw "Legacy C1-C7 Closure must remain physically blocked during R1."
}

$D4PolicyFile = Join-Path $D4Output "d4_frozen_policy.json"
if (-not (Test-Path $D4PolicyFile)) {
    throw "Frozen D4 policy is missing; no R1 model calls were started. Do not rerun D4 blindly."
}
$D4 = Get-Content $D4PolicyFile -Raw | ConvertFrom-Json
if ($D4.state -ne "FROZEN" -or [string]::IsNullOrWhiteSpace([string]$D4.model_digest)) {
    throw "Frozen D4 policy/model_digest is invalid; no R1 model calls were started."
}

Write-Host "R1 calibration real local campaign"
$Args = @(
    "-m", "inverted.harvest_d.d3_closure_r1_cli",
    "--config", $Config,
    "--output", $Output,
    "--stage-authorization", $StageAuthorization,
    "--r0-readiness-file", $R0Readiness,
    "--d4-policy-file", $D4PolicyFile
)
if ($MaxCalls -gt 0) { $Args += @("--max-calls", "$MaxCalls") }
python @Args
if ($LASTEXITCODE -ne 0) {
    throw "R1 calibration halted or failed. Preserve evidence; automatic retry is forbidden."
}
Write-Host "R1 calibration completed without a harness hard stop."
