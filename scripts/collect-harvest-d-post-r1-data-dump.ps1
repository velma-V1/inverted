param(
    [Parameter(Mandatory = $true)]
    [string]$D4Output,

    [Parameter(Mandatory = $true)]
    [string]$R1ExecutionCommit,

    [string]$OutputRoot = "runs/data-dumps/harvest-d-post-r1-20260904"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path -LiteralPath $D4Output -PathType Container)) {
    throw "Original D4 evidence directory is missing: $D4Output"
}
if (Test-Path -LiteralPath $OutputRoot) {
    $Existing = @(Get-ChildItem -LiteralPath $OutputRoot -Force -ErrorAction Stop)
    if ($Existing.Count -gt 0) {
        throw "Data dump OutputRoot is append-only and already contains files: $OutputRoot"
    }
}

$R1ExecutionCommit = (git rev-parse "$R1ExecutionCommit`^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($R1ExecutionCommit)) {
    throw "R1 execution commit does not resolve to a Git commit."
}
$PublisherCommit = (git rev-parse "HEAD^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PublisherCommit)) {
    throw "Unable to resolve current publisher commit."
}

$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("inverted-post-r1-data-dump-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

try {
    Write-Host "Post-R1 data dump: capture exact Git source snapshots"
    $R1Archive = Join-Path $TempRoot "R1-EXECUTION-SOURCE.zip"
    $PublisherArchive = Join-Path $TempRoot "POST-R1-DUMP-PUBLISHER-SOURCE.zip"

    git archive --format=zip "--output=$R1Archive" $R1ExecutionCommit
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $R1Archive -PathType Leaf)) {
        throw "Unable to archive exact R1 execution source commit."
    }
    git archive --format=zip "--output=$PublisherArchive" $PublisherCommit
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $PublisherArchive -PathType Leaf)) {
        throw "Unable to archive exact post-R1 dump publisher source commit."
    }

    $GitMetadataFile = Join-Path $TempRoot "git-metadata.json"
    $GitMetadata = [ordered]@{
        branch = ((git branch --show-current) | Out-String).Trim()
        head = $PublisherCommit
        r1_execution_commit = $R1ExecutionCommit
        status = ((git status --porcelain=v1 --branch) | Out-String).TrimEnd()
        log = ((git log --decorate --oneline -n 200) | Out-String).TrimEnd()
        remotes = ((git remote -v) | Out-String).TrimEnd()
        working_tree_diff = ((git diff --no-ext-diff) | Out-String).TrimEnd()
        staged_diff = ((git diff --cached --no-ext-diff) | Out-String).TrimEnd()
        r1_execution_commit_show = ((git show --no-patch --decorate=full --format=fuller $R1ExecutionCommit) | Out-String).TrimEnd()
        publisher_commit_show = ((git show --no-patch --decorate=full --format=fuller $PublisherCommit) | Out-String).TrimEnd()
    }
    $GitMetadata | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $GitMetadataFile -Encoding UTF8

    Write-Host "Post-R1 data dump: collect and hash complete forensic evidence"
    python -m inverted.harvest_d.post_r1_data_dump `
        --repo-root $RepoRoot `
        --d4-root $D4Output `
        --output-root $OutputRoot `
        --r1-execution-commit $R1ExecutionCommit `
        --publisher-commit $PublisherCommit `
        --git-metadata-file $GitMetadataFile `
        --source-archive "r1-execution=$R1Archive" `
        --source-archive "dump-publisher=$PublisherArchive"
    if ($LASTEXITCODE -ne 0) {
        throw "Post-R1 full data dump failed. No model inference was performed; preserve all source evidence and inspect the error."
    }

    $Zip = Join-Path $OutputRoot "INVERTED-HARVEST-D-POST-R1-FULL-DUMP.zip"
    $Sha = Join-Path $OutputRoot "INVERTED-HARVEST-D-POST-R1-FULL-DUMP.sha256"
    foreach ($Required in @($Zip, $Sha)) {
        if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) {
            throw "Post-R1 data dump returned without required output: $Required"
        }
    }

    Write-Host "POST_R1_DATA_DUMP_COMPLETE"
    Write-Host "R1 execution commit: $R1ExecutionCommit"
    Write-Host "Dump publisher commit: $PublisherCommit"
    Write-Host "ZIP: $Zip"
    Write-Host "SHA-256: $((Get-Content -LiteralPath $Sha -Raw).Trim())"
    Write-Host "No model inference was performed. R2 remains unauthorized pending dump inspection."
}
finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
