param(
    [Parameter(Mandatory = $true)]
    [string]$D4Output,

    [string]$R1Output = "runs/harvest-d-d3-closure-r1",
    [string]$Config = "configs/harvest-d-d3-closure-v2.json",
    [string]$EvidenceBranch = "evidence/harvest-d-d4-r1-20260904",
    [string]$EvidenceFolder = "harvest-d-d4-r1-20260904",
    [string]$BundleRoot = "runs/evidence-publish/harvest-d-d4-r1-20260904",
    [switch]$PackageOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-GitChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

if (-not (Test-Path -LiteralPath $D4Output -PathType Container)) {
    throw "D4 evidence directory is missing: $D4Output"
}
if (-not (Test-Path -LiteralPath $R1Output -PathType Container)) {
    throw "R1 evidence directory is missing: $R1Output"
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "Closure config is missing: $Config"
}
if (Test-Path -LiteralPath $BundleRoot) {
    $Existing = @(Get-ChildItem -LiteralPath $BundleRoot -Force -ErrorAction Stop)
    if ($Existing.Count -gt 0) {
        throw "BundleRoot already contains files. Evidence packaging is append-only; choose a new empty BundleRoot: $BundleRoot"
    }
}

$ClosureConfig = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$ExpectedQwen = [string]$ClosureConfig.models.QWEN
if ([string]::IsNullOrWhiteSpace($ExpectedQwen)) {
    throw "Closure config does not identify the expected Qwen model."
}

$ImplementationCommit = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ImplementationCommit)) {
    throw "Unable to resolve the current implementation commit."
}

Write-Host "D4/R1 evidence: validate and build immutable local archives"
python -m inverted.harvest_d.d4_r1_evidence_bundle `
    --d4-root $D4Output `
    --r1-root $R1Output `
    --output-root $BundleRoot `
    --implementation-commit $ImplementationCommit `
    --expected-qwen-model $ExpectedQwen
if ($LASTEXITCODE -ne 0) {
    throw "D4/R1 evidence validation or packaging failed. No GitHub evidence branch was created."
}

$Provenance = Join-Path $BundleRoot "evidence_provenance.json"
$ArchiveManifest = Join-Path $BundleRoot "SHA256SUMS-D4-R1-ARCHIVES.csv"
$Index = Join-Path $BundleRoot "00-HARVEST-D-D4-R1-EVIDENCE-INDEX.md"
foreach ($Required in @($Provenance, $ArchiveManifest, $Index)) {
    if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) {
        throw "Evidence bundler returned without required artifact: $Required"
    }
}

if ($PackageOnly) {
    Write-Host "D4/R1 evidence package complete (PackageOnly)."
    Write-Host "Bundle: $BundleRoot"
    exit 0
}

# Immutability gate: never overwrite or advance an existing evidence branch.
# A repeated publication must use a new branch name after independent review.
git show-ref --verify --quiet "refs/heads/$EvidenceBranch"
$LocalBranchStatus = $LASTEXITCODE
if ($LocalBranchStatus -eq 0) {
    throw "Evidence branch already exists locally: $EvidenceBranch"
}
if ($LocalBranchStatus -ne 1) {
    throw "Unable to determine whether the local evidence branch already exists."
}

git ls-remote --exit-code --heads origin "refs/heads/$EvidenceBranch" | Out-Null
$RemoteBranchStatus = $LASTEXITCODE
if ($RemoteBranchStatus -eq 0) {
    throw "Evidence branch already exists on origin: $EvidenceBranch"
}
if ($RemoteBranchStatus -ne 2) {
    throw "Unable to prove that the remote evidence branch is absent."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BundleAbsolute = (Resolve-Path -LiteralPath $BundleRoot).Path
$Worktree = Join-Path ([IO.Path]::GetTempPath()) ("inverted-d4-r1-evidence-" + [guid]::NewGuid().ToString("N"))
$WorktreeRegistered = $false

try {
    Write-Host "D4/R1 evidence: create isolated detached worktree"
    git worktree add --detach $Worktree $ImplementationCommit
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create isolated evidence worktree."
    }
    $WorktreeRegistered = $true

    # Every destructive Git operation below is scoped to the isolated worktree.
    # The active implementation checkout is never switched, reset, cleaned, or pruned.
    git -C $Worktree switch --orphan $EvidenceBranch
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create orphan evidence branch in isolated worktree."
    }

    git -C $Worktree rm -rf --ignore-unmatch . | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to clear tracked implementation files from orphan evidence worktree."
    }

    Get-ChildItem -LiteralPath $Worktree -Force |
        Where-Object { $_.Name -ne ".git" } |
        Remove-Item -Recurse -Force

    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $Worktree ".gitattributes"), "*.zip binary`n", $Utf8NoBom)

    $EvidenceRoot = Join-Path $Worktree "live-evidence"
    $Destination = Join-Path $EvidenceRoot $EvidenceFolder
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -LiteralPath (Join-Path $BundleAbsolute "*") -Destination $Destination -Recurse -Force

    # Copy-Item -LiteralPath does not expand wildcards on Windows PowerShell;
    # explicitly copy the validated bundle contents if the wildcard form yielded none.
    if (@(Get-ChildItem -LiteralPath $Destination -Force).Count -eq 0) {
        Get-ChildItem -LiteralPath $BundleAbsolute -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
        }
    }

    foreach ($RequiredName in @(
        "D4-COMPLETE-CAMPAIGN.zip",
        "R1-CALIBRATION-CAMPAIGN.zip",
        "00-HARVEST-D-D4-R1-EVIDENCE-INDEX.md",
        "SHA256SUMS-D4-R1-ARCHIVES.csv",
        "evidence_provenance.json"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $Destination $RequiredName) -PathType Leaf)) {
            throw "Isolated evidence branch staging is missing required file: $RequiredName"
        }
    }

    Invoke-GitChecked -Arguments @("-C", $Worktree, "add", ".") -FailureMessage "Unable to stage evidence branch files."
    Invoke-GitChecked -Arguments @("-C", $Worktree, "commit", "-m", "evidence: preserve Harvest D D4 and R1") -FailureMessage "Unable to commit immutable D4/R1 evidence branch."

    $EvidenceCommit = (git -C $Worktree rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($EvidenceCommit)) {
        throw "Unable to resolve evidence commit before push."
    }

    git -C $Worktree push origin "HEAD:refs/heads/$EvidenceBranch"
    if ($LASTEXITCODE -ne 0) {
        throw "Evidence commit was created locally but push failed. Preserve BundleRoot and inspect the isolated branch before retrying."
    }

    Write-Host "D4/R1 evidence published."
    Write-Host "Branch: $EvidenceBranch"
    Write-Host "Evidence commit: $EvidenceCommit"
    Write-Host "Local bundle retained: $BundleRoot"
}
finally {
    if ($WorktreeRegistered) {
        git worktree remove --force $Worktree | Out-Null
        git worktree prune | Out-Null
    } elseif (Test-Path -LiteralPath $Worktree) {
        Remove-Item -LiteralPath $Worktree -Recurse -Force -ErrorAction SilentlyContinue
    }
}
