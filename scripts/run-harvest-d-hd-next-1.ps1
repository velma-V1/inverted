param(
    [string]$Config = "configs/harvest-d-hd-next-1.json",
    [string]$Output = "runs/harvest-d-hd-next-1",
    [string]$Preregistration = "runs/harvest-d-hd-next-1-preregistration",
    [string]$OwnerAuthorization = "",
    [switch]$Execute,
    [int]$MaxCalls = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "HD-NEXT-1: focused model-free validation"
python -m pytest -q tests/test_harvest_d_hd_next1_*.py
if ($LASTEXITCODE -ne 0) { throw "HD-NEXT-1 focused validation failed; no model calls were started." }

Write-Host "HD-NEXT-1: regenerate zero-call preregistration"
python -m inverted.harvest_d.hd_next1_cli --config $Config --output $Preregistration
if ($LASTEXITCODE -ne 0) { throw "HD-NEXT-1 preregistration failed; no model calls were started." }

if (-not $Execute) {
    Write-Host "HD-NEXT-1 model-free preregistration complete. Physical execution remains blocked."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($OwnerAuthorization) -or -not (Test-Path $OwnerAuthorization)) {
    throw "Explicit owner execution authorization is required; no model calls were started."
}

Write-Host "HD-NEXT-1: owner-authorized physical campaign"
$Args = @(
    "-m", "inverted.harvest_d.hd_next1_cli",
    "--config", $Config,
    "--output", $Output,
    "--preregistration", $Preregistration,
    "--execute",
    "--owner-authorization", $OwnerAuthorization
)
if ($MaxCalls -gt 0) { $Args += @("--max-calls", [string]$MaxCalls) }
python @Args
if ($LASTEXITCODE -ne 0) { throw "HD-NEXT-1 halted or remained unresolved; no automatic retry is permitted." }
