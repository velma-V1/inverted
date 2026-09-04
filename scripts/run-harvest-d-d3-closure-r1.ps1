param(
    [string]$Config = "configs/harvest-d-d3-closure-v2.json",
    [string]$Output = "runs/harvest-d-d3-closure-r1",
    [string]$R0Output = "runs/harvest-d-d3-closure-r0-gate",
    [string]$D4Output = "runs/harvest-d-d4-qwen-policy",
    [string]$D3V1Input = "runs/harvest-d-d3",
    [string]$PostD3Output = "runs/post-d3-analysis-r1",
    [string]$StageAuthorization = "configs/harvest-d-d3-closure-v2-r1-authorization.json",
    [string]$LegacyAuthorization = "configs/harvest-d-d3-closure-v2-execution-authorization.json",
    [switch]$ModelFreeOnly,
    [int]$MaxCalls = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$FrozenD3EvidenceBranch = "evidence/harvest-d-d3-20260903"
$FrozenD3EvidenceCommit = "3d220cc5445942e22f2ac70228f8ff846a6c7230"
$FrozenD3EvidenceArchive = "live-evidence/harvest-d-d3-real-20260903-185137/D3-COMPLETE-CAMPAIGN.zip"
$FrozenD3EvidenceSha256 = "371588D6C5616D371E7EF891E939271F0AF09AC6462A0DF00F8B1486CFC4AC2B"
$FrozenD3CacheRoot = "runs/frozen-harvest-d-d3-20260903"

function Resolve-FrozenD3V1Evidence {
    param([string]$PreferredPath)

    if (Test-Path $PreferredPath) {
        return (Resolve-Path $PreferredPath).Path
    }

    Write-Host "Local D3-v1 run is absent; materializing immutable frozen evidence commit."

    git cat-file -e "$FrozenD3EvidenceCommit^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        git fetch origin $FrozenD3EvidenceBranch --no-tags --depth=1
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to fetch frozen D3-v1 evidence branch; no R1 model calls were started."
        }
        git cat-file -e "$FrozenD3EvidenceCommit^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Pinned frozen D3-v1 evidence commit is unavailable after fetch; no R1 model calls were started."
        }
    }

    if (Test-Path $FrozenD3CacheRoot) {
        Remove-Item -Recurse -Force $FrozenD3CacheRoot
    }
    New-Item -ItemType Directory -Force -Path $FrozenD3CacheRoot | Out-Null

    $Envelope = Join-Path $FrozenD3CacheRoot "frozen-d3-evidence-envelope.zip"
    $EnvelopeExtract = Join-Path $FrozenD3CacheRoot "envelope"
    $ExtractRoot = Join-Path $FrozenD3CacheRoot "real-campaign"

    git archive --format=zip "--output=$Envelope" $FrozenD3EvidenceCommit $FrozenD3EvidenceArchive
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Envelope)) {
        throw "Unable to materialize pinned frozen D3-v1 archive from Git; no R1 model calls were started."
    }

    Expand-Archive -LiteralPath $Envelope -DestinationPath $EnvelopeExtract -Force
    $ArchiveRelative = $FrozenD3EvidenceArchive.Replace('/', [IO.Path]::DirectorySeparatorChar)
    $SourceArchive = Join-Path $EnvelopeExtract $ArchiveRelative
    if (-not (Test-Path $SourceArchive)) {
        throw "Pinned frozen D3-v1 archive was not present in the evidence commit; no R1 model calls were started."
    }

    $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceArchive).Hash.ToUpperInvariant()
    if ($ActualHash -ne $FrozenD3EvidenceSha256) {
        throw "Frozen D3-v1 archive SHA-256 mismatch; no R1 model calls were started."
    }

    Expand-Archive -LiteralPath $SourceArchive -DestinationPath $ExtractRoot -Force
    $Masters = @(Get-ChildItem -LiteralPath $ExtractRoot -Recurse -File -Filter "00-HARVEST-D-D3-MASTER-INDEX.json")
    if ($Masters.Count -ne 1) {
        throw "Frozen D3-v1 archive did not resolve to exactly one real campaign root; no R1 model calls were started."
    }

    return $Masters[0].Directory.FullName
}

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

# Tie every R1 invocation, including the Windows model-free gate, back to the
# actual frozen D3-v1 real campaign. A clean implementation checkout may not
# have the historical runs/ directory, so reconstruct the immutable archive
# from its pinned evidence commit and verify its published SHA-256 before use.
Write-Host "R1 prerequisite: resolve frozen D3-v1 evidence"
$ResolvedD3V1Input = Resolve-FrozenD3V1Evidence -PreferredPath $D3V1Input
if (Test-Path $PostD3Output) { Remove-Item -Recurse -Force $PostD3Output }
Write-Host "R1 prerequisite: revalidate frozen D3-v1 historical evidence"
python -m inverted.harvest_d.post_d3_cli --input $ResolvedD3V1Input --output $PostD3Output
if ($LASTEXITCODE -ne 0) {
    throw "Post-D3 historical evidence revalidation failed; no R1 model calls were started."
}
$HistoricalGapRegistry = Join-Path $PostD3Output "post_d3_gap_registry.json"
if (-not (Test-Path $HistoricalGapRegistry)) {
    throw "post_d3_gap_registry.json was not produced; no R1 model calls were started."
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
    "--historical-gap-registry", $HistoricalGapRegistry,
    "--d4-policy-file", $D4PolicyFile
)
if ($MaxCalls -gt 0) { $Args += @("--max-calls", "$MaxCalls") }
python @Args
if ($LASTEXITCODE -ne 0) {
    throw "R1 calibration halted or failed. Preserve evidence; automatic retry is forbidden."
}
Write-Host "R1 calibration completed without a harness hard stop."
