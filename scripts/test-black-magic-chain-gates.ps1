$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Gates = Join-Path $RepoRoot "scripts\black-magic-chain-gates.ps1"
if (-not (Test-Path $Gates)) {
    throw "Missing chain gate implementation: $Gates"
}
. $Gates

function Expect-Throw([scriptblock]$Action, [string]$Label) {
    $threw = $false
    try { & $Action }
    catch { $threw = $true }
    if (-not $threw) { throw "Expected failure was not raised: $Label" }
}

function Write-Manifest([string]$Root) {
    $rows = @()
    foreach ($name in @("00-MASTER-INDEX.json", "COMPLETE-EVIDENCE.txt")) {
        $path = Join-Path $Root $name
        $hash = (Get-FileHash -Algorithm SHA256 -Path $path).Hash.ToLowerInvariant()
        $bytes = (Get-Item $path).Length
        $rows += [pscustomobject]@{ path = $name; sha256 = $hash; bytes = $bytes }
    }
    $rows | Export-Csv -Path (Join-Path $Root "SHA256SUMS.csv") -NoTypeInformation -Encoding ASCII
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("inverted-chain-gates-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
try {
    $S2 = Join-Path $TempRoot "s2"
    New-Item -ItemType Directory -Force -Path $S2 | Out-Null
    @{
        run_id = "tier-a-real"
        evidence_status = "COMPLETE"
        physical_model_calls = 720
        protocol_valid_for_primary_claim = $true
    } | ConvertTo-Json | Set-Content -Path (Join-Path $S2 "00-MASTER-INDEX.json") -Encoding ASCII
    Set-Content -Path (Join-Path $S2 "COMPLETE-EVIDENCE.txt") -Value "S2 COMPLETE" -Encoding ASCII
    Write-Manifest $S2

    Assert-S2CompletionPacket -EvidenceDir $S2 -RunId "tier-a-real" -ExpectedModelCalls 720

    $index = Get-Content (Join-Path $S2 "00-MASTER-INDEX.json") -Raw | ConvertFrom-Json
    $index.physical_model_calls = 719
    $index | ConvertTo-Json | Set-Content -Path (Join-Path $S2 "00-MASTER-INDEX.json") -Encoding ASCII
    Write-Manifest $S2
    Expect-Throw { Assert-S2CompletionPacket -EvidenceDir $S2 -RunId "tier-a-real" -ExpectedModelCalls 720 } "719 calls must not hand off"

    $index.physical_model_calls = 720
    $index.protocol_valid_for_primary_claim = $false
    $index | ConvertTo-Json | Set-Content -Path (Join-Path $S2 "00-MASTER-INDEX.json") -Encoding ASCII
    Write-Manifest $S2
    Expect-Throw { Assert-S2CompletionPacket -EvidenceDir $S2 -RunId "tier-a-real" -ExpectedModelCalls 720 } "protocol-invalid S2 must not hand off"

    $index.protocol_valid_for_primary_claim = $true
    $index | ConvertTo-Json | Set-Content -Path (Join-Path $S2 "00-MASTER-INDEX.json") -Encoding ASCII
    Write-Manifest $S2
    Add-Content -Path (Join-Path $S2 "COMPLETE-EVIDENCE.txt") -Value "tamper" -Encoding ASCII
    Expect-Throw { Assert-S2CompletionPacket -EvidenceDir $S2 -RunId "tier-a-real" -ExpectedModelCalls 720 } "tampered S2 packet must not hand off"

    $Harvest = Join-Path $TempRoot "harvest"
    New-Item -ItemType Directory -Force -Path $Harvest | Out-Null
    @{ status = "OK" } | ConvertTo-Json | Set-Content -Path (Join-Path $Harvest "integrity.json") -Encoding ASCII
    @{ completion = @{ pass = $true } } | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $Harvest "metrics.json") -Encoding ASCII
    Assert-HarvestCompletionPacket -EvidenceDir $Harvest -Label "Harvest A"

    @{ completion = @{ pass = $false } } | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $Harvest "metrics.json") -Encoding ASCII
    Expect-Throw { Assert-HarvestCompletionPacket -EvidenceDir $Harvest -Label "Harvest A" } "completion=false must not hand off"

    Write-Host "BLACK_MAGIC_CHAIN_GATES_OK"
}
finally {
    Remove-Item -Recurse -Force $TempRoot -ErrorAction SilentlyContinue
}
