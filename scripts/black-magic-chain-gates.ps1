Set-StrictMode -Version Latest

function Assert-ChainFile([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing required file: $Path"
    }
}

function Assert-ChainSha256Manifest([string]$EvidenceDir) {
    $root = [System.IO.Path]::GetFullPath($EvidenceDir).TrimEnd('\') + '\'
    $manifest = Join-Path $EvidenceDir "SHA256SUMS.csv"
    Assert-ChainFile $manifest "Evidence packet"
    $rows = @(Import-Csv -LiteralPath $manifest)
    if ($rows.Count -lt 1) { throw "Evidence packet SHA256SUMS.csv is empty" }

    foreach ($row in $rows) {
        $relative = [string]$row.path
        if ([string]::IsNullOrWhiteSpace($relative) -or [System.IO.Path]::IsPathRooted($relative)) {
            throw "Evidence manifest contains invalid path: $relative"
        }
        $path = [System.IO.Path]::GetFullPath((Join-Path $EvidenceDir $relative))
        if (-not $path.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Evidence manifest path escapes packet root: $relative"
        }
        Assert-ChainFile $path "Evidence manifest"
        $expected = ([string]$row.sha256).Trim().ToLowerInvariant()
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
        if ($expected -ne $actual) {
            throw "Evidence manifest SHA256 mismatch: $relative"
        }
        if ($null -ne $row.bytes -and ([string]$row.bytes).Trim() -ne "") {
            $expectedBytes = [int64]$row.bytes
            $actualBytes = (Get-Item -LiteralPath $path).Length
            if ($expectedBytes -ne $actualBytes) {
                throw "Evidence manifest byte-count mismatch: $relative"
            }
        }
    }
}

function Assert-S2CompletionPacket {
    param(
        [Parameter(Mandatory=$true)][string]$EvidenceDir,
        [Parameter(Mandatory=$true)][string]$RunId,
        [int]$ExpectedModelCalls = 720
    )

    $indexPath = Join-Path $EvidenceDir "00-MASTER-INDEX.json"
    $completePath = Join-Path $EvidenceDir "COMPLETE-EVIDENCE.txt"
    Assert-ChainFile $indexPath "S2"
    Assert-ChainFile $completePath "S2"

    $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
    if ([string]$index.run_id -ne $RunId) {
        throw "S2 run_id mismatch: expected $RunId, got $($index.run_id)"
    }
    if ([string]$index.evidence_status -ne "COMPLETE") {
        throw "S2 evidence is not COMPLETE: $($index.evidence_status)"
    }
    if ([int]$index.physical_model_calls -ne $ExpectedModelCalls) {
        throw "S2 physical model calls mismatch: expected $ExpectedModelCalls, got $($index.physical_model_calls)"
    }
    if ($index.protocol_valid_for_primary_claim -ne $true) {
        throw "S2 protocol_valid_for_primary_claim is not true"
    }
    if ((Get-Item -LiteralPath $completePath).Length -le 0) {
        throw "S2 COMPLETE-EVIDENCE.txt is empty"
    }
    Assert-ChainSha256Manifest -EvidenceDir $EvidenceDir
    return $index
}

function Assert-HarvestCompletionPacket {
    param(
        [Parameter(Mandatory=$true)][string]$EvidenceDir,
        [Parameter(Mandatory=$true)][string]$Label
    )

    $integrityPath = Join-Path $EvidenceDir "integrity.json"
    $metricsPath = Join-Path $EvidenceDir "metrics.json"
    Assert-ChainFile $integrityPath $Label
    Assert-ChainFile $metricsPath $Label

    $integrity = Get-Content -LiteralPath $integrityPath -Raw | ConvertFrom-Json
    $metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
    if ([string]$integrity.status -ne "OK") {
        throw "$Label integrity is not OK: $($integrity.status)"
    }
    if ($null -eq $metrics.completion -or $metrics.completion.pass -ne $true) {
        throw "$Label completion gate did not pass"
    }
    return [pscustomobject]@{ integrity = $integrity; metrics = $metrics }
}

function Test-BlackMagicChainContinuation {
    param(
        [Parameter(Mandatory=$true)][bool]$StageSucceeded,
        [Parameter(Mandatory=$true)][bool]$ContinueOnStageFailure
    )

    return ($StageSucceeded -or $ContinueOnStageFailure)
}
