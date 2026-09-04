param(
    [string]$D4Config = "configs/harvest-d-d4-qwen-policy.json",
    [string]$D4Output = "runs/harvest-d-d4-qwen-policy",
    [string]$ClosureConfig = "configs/harvest-d-d3-closure-v2.json",
    [string]$ClosureOutput = "runs/harvest-d-d3-closure-v2",
    [string]$D3V1Input = "runs/harvest-d-d3",
    [string]$PostD3Output = "runs/post-d3-analysis",
    [string]$ExecutionAuthorization = "configs/harvest-d-d3-closure-v2-execution-authorization.json",
    [string]$StateOutput = "runs/harvest-d-d4-through-closure",
    [switch]$ModelFreeOnly,
    [int]$D4MaxCalls = 0,
    [int]$ClosureMaxCalls = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$D4Launcher = ".\scripts\run-harvest-d-d4-qwen-policy.ps1"
$ClosureLauncher = ".\scripts\run-harvest-d-d3-closure-v2.ps1"

function Invoke-CheckedLauncher {
    param(
        [string]$ScriptPath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Read-RequiredJson {
    param(
        [string]$Path,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label is missing: $Path"
    }
    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    } catch {
        throw "$Label is invalid JSON: $Path"
    }
}

function Write-ChainState {
    param(
        [string]$State,
        [string]$Reason,
        [object]$ClosureAuthorized
    )
    if (-not (Test-Path -LiteralPath $StateOutput)) {
        New-Item -ItemType Directory -Force -Path $StateOutput | Out-Null
    }
    $Payload = [ordered]@{
        protocol = "D4-THROUGH-D3-CLOSURE-v1"
        state = $State
        d4_output = $D4Output
        closure_output = $ClosureOutput
        closure_physical_execution_authorized = $ClosureAuthorized
        reason = $Reason
    }
    $StatePath = Join-Path $StateOutput "00-D4-THROUGH-CLOSURE-STATE.json"
    $Json = $Payload | ConvertTo-Json -Depth 6
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($StatePath, $Json + [Environment]::NewLine, $Utf8NoBom)
}

if ($ModelFreeOnly) {
    Write-Host "D4->Closure chain: D4 model-free gate"
    $D4Args = @(
        "-Config", $D4Config,
        "-Output", $D4Output,
        "-D3V1Input", $D3V1Input,
        "-PostD3Output", $PostD3Output,
        "-ModelFreeOnly"
    )
    Invoke-CheckedLauncher -ScriptPath $D4Launcher -Arguments $D4Args -FailureMessage "Combined chain D4 model-free gate failed."

    Write-Host "D4->Closure chain: Closure model-free gate"
    $ClosureArgs = @(
        "-Config", $ClosureConfig,
        "-Output", $ClosureOutput,
        "-D4Output", $D4Output,
        "-D3V1Input", $D3V1Input,
        "-PostD3Output", $PostD3Output,
        "-ExecutionAuthorization", $ExecutionAuthorization,
        "-ModelFreeOnly"
    )
    Invoke-CheckedLauncher -ScriptPath $ClosureLauncher -Arguments $ClosureArgs -FailureMessage "Combined chain Closure model-free gate failed."
    Write-ChainState -State "MODEL_FREE_COMPLETE" -Reason "Both real launchers passed their zero-call paths." -ClosureAuthorized $null
    Write-Host "D4->Closure chain model-free gate complete."
    exit 0
}

Write-Host "D4->Closure chain: D4 real campaign"
$D4Args = @(
    "-Config", $D4Config,
    "-Output", $D4Output,
    "-D3V1Input", $D3V1Input,
    "-PostD3Output", $PostD3Output
)
if ($D4MaxCalls -gt 0) {
    $D4Args += @("-MaxCalls", [string]$D4MaxCalls)
}
Invoke-CheckedLauncher -ScriptPath $D4Launcher -Arguments $D4Args -FailureMessage "D4 did not freeze a valid Qwen policy; Closure was not opened."

$D4PolicyFile = Join-Path $D4Output "d4_frozen_policy.json"
$D4Policy = Read-RequiredJson -Path $D4PolicyFile -Label "D4 frozen policy"
if ([string]$D4Policy.state -ne "FROZEN") {
    throw "D4 policy is not FROZEN; Closure was not opened."
}
if ([string]::IsNullOrWhiteSpace([string]$D4Policy.model_id)) {
    throw "D4 frozen policy is missing model identity; Closure was not opened."
}
if ([string]::IsNullOrWhiteSpace([string]$D4Policy.model_digest)) {
    throw "D4 frozen policy is missing the exact model_digest; Closure was not opened."
}
if (@("DEFAULT", "THINK_OFF") -notcontains [string]$D4Policy.policy_id) {
    throw "D4 frozen policy has an unsupported policy_id; Closure was not opened."
}

Write-Host "D4->Closure chain: Closure readiness gate"
$ClosureReadinessArgs = @(
    "-Config", $ClosureConfig,
    "-Output", $ClosureOutput,
    "-D4Output", $D4Output,
    "-D3V1Input", $D3V1Input,
    "-PostD3Output", $PostD3Output,
    "-ExecutionAuthorization", $ExecutionAuthorization,
    "-ModelFreeOnly"
)
Invoke-CheckedLauncher -ScriptPath $ClosureLauncher -Arguments $ClosureReadinessArgs -FailureMessage "Closure readiness/model-free gate failed after D4."

$Authorization = Read-RequiredJson -Path $ExecutionAuthorization -Label "D3-Closure execution authorization"
if ([string]$Authorization.protocol -ne "D3-CLOSURE-v2") {
    throw "D3-Closure execution authorization protocol mismatch."
}
if ($Authorization.physical_execution_authorized -ne $true) {
    $Reason = [string]$Authorization.reason
    Write-ChainState -State "D4_COMPLETE_CLOSURE_SCIENTIFIC_HOLD" -Reason $Reason -ClosureAuthorized $false
    Write-Host "D4->Closure chain state: D4_COMPLETE_CLOSURE_SCIENTIFIC_HOLD"
    Write-Host "D4 is complete and Closure readiness opened correctly. Closure physical inference remains scientifically blocked: $Reason"
    exit 0
}

$ClosureGateOutput = "$ClosureOutput-model-free-gate"
$AdequacyReport = Join-Path $ClosureGateOutput "closure_claim_adequacy_report.json"
$Adequacy = Read-RequiredJson -Path $AdequacyReport -Label "Fresh Closure claim-adequacy report"
if ($Adequacy.physical_execution_authorized -ne $true) {
    $Blockers = @($Adequacy.blockers) -join "; "
    $Reason = "Fresh Closure claim-adequacy gate did not authorize physical execution. $Blockers"
    Write-ChainState -State "D4_COMPLETE_CLOSURE_SCIENTIFIC_HOLD" -Reason $Reason -ClosureAuthorized $false
    Write-Host "D4->Closure chain state: D4_COMPLETE_CLOSURE_SCIENTIFIC_HOLD"
    Write-Host $Reason
    exit 0
}

Write-Host "D4->Closure chain: Closure real campaign"
$ClosureArgs = @(
    "-Config", $ClosureConfig,
    "-Output", $ClosureOutput,
    "-D4Output", $D4Output,
    "-D3V1Input", $D3V1Input,
    "-PostD3Output", $PostD3Output,
    "-ExecutionAuthorization", $ExecutionAuthorization
)
if ($ClosureMaxCalls -gt 0) {
    $ClosureArgs += @("-MaxCalls", [string]$ClosureMaxCalls)
}
Invoke-CheckedLauncher -ScriptPath $ClosureLauncher -Arguments $ClosureArgs -FailureMessage "Closure campaign halted or failed after a valid D4 handoff. Inspect preserved evidence; no automatic retry is permitted."

$ClosureMasterFile = Join-Path $ClosureOutput "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json"
$ClosureMaster = Read-RequiredJson -Path $ClosureMasterFile -Label "D3-Closure master index"
if ([string]$ClosureMaster.final_state -ne "COMPLETE" -or $ClosureMaster.scientific_complete -ne $true) {
    throw "Closure launcher returned without a scientifically COMPLETE master state."
}

Write-ChainState -State "COMPLETE" -Reason "D4 policy frozen and D3-Closure completed under fresh authorization." -ClosureAuthorized $true
Write-Host "D4->Closure chain complete."
