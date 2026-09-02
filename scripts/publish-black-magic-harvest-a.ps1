param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$EvidenceRoot,
    [Parameter(Mandatory = $true)][string]$StagingRoot,
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$CodeSha,
    [Parameter(Mandatory = $true)][string]$StopSignal,
    [int]$TotalActions = 1200,
    [int]$PublishEveryActions = 225,
    [int]$PublishEverySeconds = 300,
    [int]$PollSeconds = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Branch = "evidence/harvest-a-$RunId"
$LocalBranch = "checkpoint-harvest-a-$RunId"
$StagingRepo = Join-Path $StagingRoot "$RunId-github"
$ResultRoot = Join-Path $StagingRepo "live-evidence\harvest-a\$RunId"
$CurrentRoot = Join-Path $ResultRoot "current"
$ProgressPath = Join-Path $ResultRoot "progress.json"
$PublisherLog = Join-Path $StagingRoot "$RunId-publisher.log"
$ActionLedger = Join-Path $EvidenceRoot "external_actions.jsonl"

function Log([string]$Message) {
    $parent = Split-Path -Parent $PublisherLog
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $line = "[$([DateTime]::UtcNow.ToString('o'))] $Message"
    Add-Content -Path $PublisherLog -Value $line -Encoding UTF8
    Write-Host $line
}

function Run-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& git @GitArgs 2>&1)
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
    return [pscustomobject]@{ ExitCode = $code; Output = $output }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$GitArgs,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $result = Run-Git -GitArgs $GitArgs
    foreach ($line in $result.Output) { Log "$Label`: $line" }
    if ($result.ExitCode -ne 0) { throw "$Label`_FAILED:$($result.ExitCode)" }
}

function Get-LineCount([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $count = 0
    $reader = [System.IO.File]::OpenText($Path)
    try {
        while ($null -ne $reader.ReadLine()) { $count++ }
    }
    finally {
        $reader.Dispose()
    }
    return $count
}

function Ensure-StagingRepo {
    if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
        throw "SOURCE_REPOSITORY_NOT_FOUND:$RepoPath"
    }

    New-Item -ItemType Directory -Force -Path $StagingRoot | Out-Null
    if (Test-Path (Join-Path $StagingRepo ".git")) {
        Log "Reusing isolated Harvest A staging repo: $StagingRepo"
        return
    }

    if (Test-Path $StagingRepo) {
        Remove-Item $StagingRepo -Recurse -Force
    }

    $originResult = Run-Git -GitArgs @("-C", $RepoPath, "remote", "get-url", "origin")
    if ($originResult.ExitCode -ne 0) { throw "GIT_ORIGIN_LOOKUP_FAILED:$($originResult.ExitCode)" }
    $origin = (($originResult.Output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
    if (-not $origin) { throw "GIT_ORIGIN_LOOKUP_EMPTY" }

    Invoke-Git -GitArgs @("clone", "--no-hardlinks", "--no-checkout", $RepoPath, $StagingRepo) -Label "GIT_CLONE_LOCAL_STAGING"
    Invoke-Git -GitArgs @("-C", $StagingRepo, "remote", "set-url", "origin", $origin) -Label "GIT_SET_REAL_ORIGIN"
    Invoke-Git -GitArgs @("-C", $StagingRepo, "checkout", "-B", $LocalBranch, $CodeSha) -Label "GIT_CHECKOUT_CODE_SHA"
    Log "Staging repo ready. evidence_branch=$Branch code_sha=$CodeSha"
}

function Copy-EvidenceSnapshot {
    New-Item -ItemType Directory -Force -Path $ResultRoot | Out-Null
    if (Test-Path $CurrentRoot) {
        Remove-Item $CurrentRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $CurrentRoot | Out-Null

    if (-not (Test-Path $EvidenceRoot)) { return }
    $items = @(Get-ChildItem -Path $EvidenceRoot -Force -ErrorAction SilentlyContinue)
    foreach ($item in $items) {
        Copy-Item -Path $item.FullName -Destination (Join-Path $CurrentRoot $item.Name) -Recurse -Force
    }
}

function Get-FinalState {
    $integrityPath = Join-Path $EvidenceRoot "integrity.json"
    $manifestPath = Join-Path $EvidenceRoot "SHA256SUMS.csv"
    $finalVerified = $false
    $integrityStatus = $null
    $manifestHash = $null

    if (Test-Path $integrityPath) {
        try {
            $integrity = Get-Content $integrityPath -Raw | ConvertFrom-Json
            $integrityStatus = [string]$integrity.status
            $finalVerified = ($integrityStatus -eq "OK") -and (Test-Path $manifestPath)
        }
        catch {
            $integrityStatus = "UNREADABLE"
        }
    }
    if (Test-Path $manifestPath) {
        $manifestHash = (Get-FileHash -Algorithm SHA256 -Path $manifestPath).Hash.ToLowerInvariant()
    }

    return [pscustomobject]@{
        FinalVerified = $finalVerified
        IntegrityStatus = $integrityStatus
        ManifestHash = $manifestHash
    }
}

function Commit-And-Push([string]$Reason) {
    Invoke-Git -GitArgs @("-C", $StagingRepo, "add", "--", "live-evidence/harvest-a/$RunId") -Label "GIT_ADD_EVIDENCE"
    $diff = Run-Git -GitArgs @("-C", $StagingRepo, "diff", "--cached", "--quiet")
    if ($diff.ExitCode -gt 1) { throw "GIT_DIFF_FAILED:$($diff.ExitCode)" }
    if ($diff.ExitCode -eq 0) {
        Log "No evidence changes to publish."
        return
    }

    Invoke-Git -GitArgs @(
        "-C", $StagingRepo,
        "-c", "user.name=inverted-harvest-checkpoint",
        "-c", "user.email=inverted-harvest-checkpoint@users.noreply.github.com",
        "commit", "-m", "evidence: Harvest A $RunId $Reason"
    ) -Label "GIT_COMMIT_EVIDENCE"

    $push = Run-Git -GitArgs @("-C", $StagingRepo, "push", "-u", "origin", "HEAD:$Branch")
    foreach ($line in $push.Output) { Log "GIT_PUSH_EVIDENCE: $line" }
    if ($push.ExitCode -ne 0) { throw "GIT_PUSH_EVIDENCE_FAILED:$($push.ExitCode)" }
    Log "REMOTE HARVEST A CHECKPOINT VERIFIED branch=$Branch reason=$Reason"
}

function Publish([bool]$FinalSignal) {
    $completed = Get-LineCount $ActionLedger
    Copy-EvidenceSnapshot
    $finalState = Get-FinalState

    $progress = [ordered]@{
        run_id = $RunId
        experiment = "decision_harvest"
        branch = $Branch
        code_sha = $CodeSha
        external_actions_completed = $completed
        total_action_ceiling = $TotalActions
        percent_of_ceiling = if ($TotalActions -gt 0) { [Math]::Round(100.0 * $completed / $TotalActions, 4) } else { 0.0 }
        checkpoint_policy = [ordered]@{
            publish_every_actions = $PublishEveryActions
            publish_every_seconds = $PublishEverySeconds
        }
        final_signal_seen = $FinalSignal
        final_verified = [bool]$finalState.FinalVerified
        integrity_status = $finalState.IntegrityStatus
        sha256_manifest_hash = $finalState.ManifestHash
        source_evidence_root = $EvidenceRoot
        updated_utc = [DateTime]::UtcNow.ToString("o")
    }
    $progress | ConvertTo-Json -Depth 8 | Set-Content -Path $ProgressPath -Encoding UTF8

    $reason = if ($FinalSignal) {
        if ($finalState.FinalVerified) { "FINAL VERIFIED actions=$completed" } else { "FINAL SIGNAL partial actions=$completed" }
    } else {
        "checkpoint actions=$completed"
    }
    Commit-And-Push $reason
    $script:LastPublishedActions = $completed
    $script:LastPublishedAt = [DateTime]::UtcNow
}

try {
    Log "HARVEST_A_CHECKPOINT_PUBLISHER starting run=$RunId"
    Ensure-StagingRepo
    $script:LastPublishedActions = -1
    $script:LastPublishedAt = [DateTime]::UtcNow.AddSeconds(-$PublishEverySeconds)

    while ($true) {
        $stop = Test-Path $StopSignal
        $completed = Get-LineCount $ActionLedger
        $newActions = $completed - $script:LastPublishedActions
        $elapsed = ([DateTime]::UtcNow - $script:LastPublishedAt).TotalSeconds
        $actionDue = ($script:LastPublishedActions -lt 0) -or ($newActions -ge $PublishEveryActions)
        $timeDue = ($completed -gt $script:LastPublishedActions) -and ($elapsed -ge $PublishEverySeconds)

        if ($stop -or $actionDue -or $timeDue) {
            try {
                Publish -FinalSignal:$stop
            }
            catch {
                Log "CHECKPOINT PUBLISH FAILED (local run continues): $($_.Exception.Message)"
            }
        }

        if ($stop) { break }
        Start-Sleep -Seconds $PollSeconds
    }

    Log "HARVEST_A_CHECKPOINT_PUBLISHER stopped. Local evidence untouched: $EvidenceRoot"
}
catch {
    Log "HARVEST_A_CHECKPOINT_PUBLISHER FATAL (local run continues): $($_.Exception.Message)"
    exit 0
}
