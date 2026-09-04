$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Publisher = Join-Path $RepoRoot "scripts/preserve-harvest-d-d4-r1-evidence.ps1"
$FixtureTest = Join-Path $RepoRoot "tests/test_harvest_d_d4_r1_evidence_bundle.py"
$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("inverted-d4-r1-evidence-publisher-test-" + [guid]::NewGuid().ToString("N"))
$Remote = Join-Path $TempRoot "remote.git"
$WorkRepo = Join-Path $TempRoot "repo"
$D4 = Join-Path $TempRoot "d4"
$R1 = Join-Path $TempRoot "r1"
$Bundle = Join-Path $TempRoot "bundle"
$Config = Join-Path $WorkRepo "closure-config.json"
$EvidenceBranch = "evidence/ci-d4-r1-publisher"
$EvidenceFolder = "ci-d4-r1-publisher"
$LocationPushed = $false

function Invoke-GitChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & git @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

try {
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
    Invoke-GitChecked -Arguments @("init", "--bare", $Remote) -FailureMessage "Unable to initialize temporary bare remote."
    Invoke-GitChecked -Arguments @("init", $WorkRepo) -FailureMessage "Unable to initialize temporary publisher repository."
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "config", "user.email", "inverted-ci@example.invalid") -FailureMessage "Unable to configure test Git email."
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "config", "user.name", "INVERTED CI") -FailureMessage "Unable to configure test Git user."
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "remote", "add", "origin", $Remote) -FailureMessage "Unable to configure temporary origin."

    [System.IO.File]::WriteAllText((Join-Path $WorkRepo "run-baseline.txt"), "R1 execution baseline`n")
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "add", "run-baseline.txt") -FailureMessage "Unable to stage execution baseline."
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "commit", "-m", "test: synthetic R1 execution commit") -FailureMessage "Unable to create synthetic R1 execution commit."
    $R1ExecutionCommit = (git -C $WorkRepo rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($R1ExecutionCommit)) {
        throw "Unable to resolve synthetic R1 execution commit."
    }

    [System.IO.File]::WriteAllText((Join-Path $WorkRepo "publisher-implementation.txt"), "publisher added after R1`n")
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "add", "publisher-implementation.txt") -FailureMessage "Unable to stage publisher implementation marker."
    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "commit", "-m", "test: synthetic publisher commit") -FailureMessage "Unable to create synthetic publisher commit."
    $PublisherCommit = (git -C $WorkRepo rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PublisherCommit)) {
        throw "Unable to resolve synthetic publisher commit."
    }
    if ($PublisherCommit -eq $R1ExecutionCommit) {
        throw "Synthetic provenance test failed to create distinct execution and publisher commits."
    }

    Invoke-GitChecked -Arguments @("-C", $WorkRepo, "push", "-u", "origin", "HEAD:refs/heads/main") -FailureMessage "Unable to seed temporary origin main branch."

    $ConfigPayload = @{ models = @{ QWEN = "qwen3.5:9b-q8_0" } } | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($Config, $ConfigPayload + "`n")

    $FixtureCode = @"
from pathlib import Path
import runpy
module = runpy.run_path(r'''$FixtureTest''')
module['_write_d4'](Path(r'''$D4'''))
module['_write_r1'](Path(r'''$R1'''))
"@
    $FixtureCode | python -
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create checksum-valid synthetic D4/R1 evidence fixtures."
    }

    Push-Location $WorkRepo
    $LocationPushed = $true

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Publisher `
        -D4Output $D4 `
        -R1ExecutionCommit $R1ExecutionCommit `
        -R1Output $R1 `
        -Config $Config `
        -EvidenceBranch $EvidenceBranch `
        -EvidenceFolder $EvidenceFolder `
        -BundleRoot $Bundle
    if ($LASTEXITCODE -ne 0) {
        throw "D4/R1 evidence publisher integration execution failed."
    }

    $ActiveHead = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $ActiveHead -ne $PublisherCommit) {
        throw "Publisher mutated or switched the active checkout."
    }

    git --git-dir $Remote show-ref --verify --quiet "refs/heads/$EvidenceBranch"
    if ($LASTEXITCODE -ne 0) {
        throw "Evidence branch was not pushed to the temporary bare remote."
    }

    $RemoteCommitLine = (git --git-dir $Remote rev-list --parents -n 1 "refs/heads/$EvidenceBranch").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RemoteCommitLine)) {
        throw "Unable to inspect published evidence commit."
    }
    if (($RemoteCommitLine -split "\s+").Count -ne 1) {
        throw "Published evidence branch is not an orphan-root commit."
    }

    $Tree = @(git --git-dir $Remote ls-tree -r --name-only "refs/heads/$EvidenceBranch")
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect published evidence tree."
    }
    $ExpectedPrefix = "live-evidence/$EvidenceFolder/"
    foreach ($RequiredName in @(
        "D4-COMPLETE-CAMPAIGN.zip",
        "R1-CALIBRATION-CAMPAIGN.zip",
        "00-HARVEST-D-D4-R1-EVIDENCE-INDEX.md",
        "SHA256SUMS-D4-R1-ARCHIVES.csv",
        "evidence_provenance.json"
    )) {
        if ($Tree -notcontains ($ExpectedPrefix + $RequiredName)) {
            throw "Published evidence branch is missing required artifact: $RequiredName"
        }
    }
    if ($Tree -contains "run-baseline.txt" -or $Tree -contains "publisher-implementation.txt") {
        throw "Evidence branch leaked implementation-history files instead of remaining evidence-only."
    }

    $ProvenancePath = Join-Path $Bundle "evidence_provenance.json"
    if (-not (Test-Path -LiteralPath $ProvenancePath -PathType Leaf)) {
        throw "Local evidence bundle was not retained."
    }
    $Provenance = Get-Content -LiteralPath $ProvenancePath -Raw | ConvertFrom-Json
    if ([string]$Provenance.r1_execution_commit -ne $R1ExecutionCommit) {
        throw "Preserved provenance does not identify the R1 execution commit."
    }
    if ([string]$Provenance.implementation_commit -ne $R1ExecutionCommit) {
        throw "Compatibility implementation_commit alias diverges from R1 execution provenance."
    }
    if ($Provenance.source_mutation_observed -ne $false) {
        throw "Publisher reported source evidence mutation."
    }
    if ($Provenance.model_inference_performed -ne $false) {
        throw "Publisher reported model inference during evidence preservation."
    }

    Write-Host "INVERTED_D4_R1_EVIDENCE_PUBLISHER_INTEGRATION_OK"
}
finally {
    if ($LocationPushed) {
        Pop-Location
    }
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
