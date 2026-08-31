param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$RunRoot,
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Checkpoint,
    [Parameter(Mandatory = $true)][string]$StopSignal,
    [Parameter(Mandatory = $true)][string]$FinalRunDir,
    [int]$TotalTrials = 6480,
    [int]$PublishEverySeconds = 300,
    [int]$PollSeconds = 15
)

$ErrorActionPreference = "Stop"
$Branch = "results-$RunId"
$LocalBranch = "checkpoint-$RunId"
$StagingRepo = Join-Path $RunRoot "$RunId-github"
$ResultRoot = Join-Path $StagingRepo "live-results\$RunId"
$ChunkRoot = Join-Path $ResultRoot "chunks"
$ProgressPath = Join-Path $ResultRoot "progress.json"
$PublisherLog = Join-Path $RunRoot "$RunId-github-publisher.log"
$FailureLog = Join-Path $RunRoot "$RunId.call-failures.jsonl"
$RemoteFailureLog = Join-Path $ResultRoot "call-failures.jsonl"
$RequiredArtifacts = @("events.jsonl","model_calls.jsonl","trials.csv","trials.jsonl","failures.csv","summary.json","summary.csv","report.txt","config.json","provenance.json")

function Log([string]$Message) {
    $line = "[$([DateTime]::UtcNow.ToString('o'))] $Message"
    $line | Tee-Object -FilePath $PublisherLog -Append
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$GitArgs,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $output = & git @GitArgs 2>&1
    $code = $LASTEXITCODE
    foreach ($line in $output) { Log "$Label`: $line" }
    if ($code -ne 0) { throw "$Label`_FAILED:$code" }
}

function Get-LineCount([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $count = 0
    $reader = [System.IO.File]::OpenText($Path)
    try { while ($null -ne $reader.ReadLine()) { $count++ } } finally { $reader.Dispose() }
    return $count
}

function Test-FinalArtifactsReady {
    if (-not (Test-Path $FinalRunDir)) { return $false }
    foreach ($name in $RequiredArtifacts) {
        if (-not (Test-Path (Join-Path $FinalRunDir $name))) { return $false }
    }
    return $true
}

function Write-CheckpointChunk([string]$Source, [int]$StartLine, [int]$EndLine, [string]$Destination) {
    $reader = [System.IO.File]::OpenText($Source)
    $writer = New-Object System.IO.StreamWriter($Destination, $false, (New-Object System.Text.UTF8Encoding($false)))
    $lineNumber = 0
    try {
        while ($null -ne ($line = $reader.ReadLine())) {
            $lineNumber++
            if ($lineNumber -lt $StartLine) { continue }
            if ($lineNumber -gt $EndLine) { break }
            $writer.WriteLine($line)
        }
    } finally {
        $writer.Dispose()
        $reader.Dispose()
    }
}

function Ensure-StagingRepo {
    if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
        throw "INVERTED_REPO_NOT_FOUND:$RepoPath"
    }
    if (Test-Path (Join-Path $StagingRepo ".git")) {
        Log "Reusing isolated checkpoint staging repo: $StagingRepo"
        return
    }
    if (Test-Path $StagingRepo) { Remove-Item $StagingRepo -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $StagingRepo | Out-Null

    $origin = (& git -C $RepoPath remote get-url origin 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $origin) { throw "GIT_ORIGIN_LOOKUP_FAILED:$LASTEXITCODE" }

    Invoke-Git -GitArgs @("init", $StagingRepo) -Label "GIT_INIT_STAGING"
    Invoke-Git -GitArgs @("-C", $StagingRepo, "remote", "add", "origin", $origin) -Label "GIT_ADD_REMOTE"
    Invoke-Git -GitArgs @("-C", $StagingRepo, "fetch", "--depth=1", "origin", "main") -Label "GIT_FETCH_MAIN"
    Invoke-Git -GitArgs @("-C", $StagingRepo, "checkout", "-B", $LocalBranch, "FETCH_HEAD") -Label "GIT_CHECKOUT_STAGING"
    Log "Checkpoint staging repo ready; remote result branch=$Branch"
}

function Commit-And-Push([string]$Reason) {
    Invoke-Git -GitArgs @("-C", $StagingRepo, "add", "--", "live-results/$RunId") -Label "GIT_ADD_CHECKPOINT"

    & git -C $StagingRepo diff --cached --quiet
    $hasChanges = ($LASTEXITCODE -ne 0)
    if ($hasChanges) {
        Invoke-Git -GitArgs @("-C", $StagingRepo, "-c", "user.name=inverted-checkpoint", "-c", "user.email=inverted-checkpoint@users.noreply.github.com", "commit", "-m", "results: $RunId $Reason") -Label "GIT_COMMIT_CHECKPOINT"
    }

    $output = & git -C $StagingRepo push --force-with-lease origin "HEAD:$Branch" 2>&1
    $code = $LASTEXITCODE
    foreach ($line in $output) { Log "git push: $line" }
    if ($code -ne 0) {
        $output = & git -C $StagingRepo push origin "HEAD:$Branch" 2>&1
        $code = $LASTEXITCODE
        foreach ($line in $output) { Log "git push fallback: $line" }
    }
    if ($code -ne 0) { throw "GIT_PUSH_CHECKPOINT_FAILED:$code" }
    Log "REMOTE CHECKPOINT VERIFIED branch=$Branch reason=$Reason"
}

function Publish-Checkpoint([bool]$ForceFinal = $false) {
    $completed = Get-LineCount $Checkpoint
    $newChunk = $completed -gt $script:LastPublished
    $chunkName = $null
    $hash = $null

    if ($newChunk) {
        New-Item -ItemType Directory -Force -Path $ChunkRoot | Out-Null
        $start = $script:LastPublished + 1
        $end = $completed
        $chunkName = "checkpoint-{0:D6}-{1:D6}.jsonl" -f $start, $end
        $chunkPath = Join-Path $ChunkRoot $chunkName
        Write-CheckpointChunk $Checkpoint $start $end $chunkPath
        $hash = (Get-FileHash -Algorithm SHA256 -Path $chunkPath).Hash
    }

    $failureCount = Get-LineCount $FailureLog
    $failureHash = $null
    if (Test-Path $FailureLog) {
        Copy-Item $FailureLog $RemoteFailureLog -Force
        $failureHash = (Get-FileHash -Algorithm SHA256 -Path $FailureLog).Hash
    }

    $progress = [ordered]@{
        run_id = $RunId
        branch = $Branch
        completed = $completed
        total = $TotalTrials
        percent = if ($TotalTrials -gt 0) { [Math]::Round(100.0 * $completed / $TotalTrials, 4) } else { 100.0 }
        last_chunk = $chunkName
        last_chunk_sha256 = $hash
        failed_call_records = $failureCount
        failed_call_log_sha256 = $failureHash
        updated_utc = [DateTime]::UtcNow.ToString("o")
        final_signal_seen = $ForceFinal
        local_checkpoint = $Checkpoint
    }
    $progress | ConvertTo-Json -Depth 6 | Set-Content -Path $ProgressPath -Encoding UTF8

    $reason = if ($newChunk) { "checkpoint $($script:LastPublished + 1)-$completed" } else { "telemetry refresh $completed" }
    Commit-And-Push $reason
    if ($newChunk) {
        $script:LastPublished = $completed
        Log "Published checkpoint through row $completed SHA256=$hash"
    }
    if ($failureCount -gt 0) {
        Log "Published failed-call telemetry rows=$failureCount SHA256=$failureHash"
    }
}

function Publish-FinalArtifacts {
    if (-not (Test-Path $FinalRunDir)) {
        Log "Final run directory does not exist; checkpoint-only publication retained."
        return
    }
    $finalRoot = Join-Path $ResultRoot "final"
    New-Item -ItemType Directory -Force -Path $finalRoot | Out-Null
    $copied = 0
    foreach ($name in $RequiredArtifacts) {
        $source = Join-Path $FinalRunDir $name
        if (Test-Path $source) {
            Copy-Item $source (Join-Path $finalRoot $name) -Force
            $copied++
        }
    }
    if ($copied -eq $RequiredArtifacts.Count) {
        Commit-And-Push "final complete artifact bundle"
        Log "Published all $copied final benchmark artifacts."
    } else {
        Log "Final bundle incomplete ($copied/$($RequiredArtifacts.Count)); not labeling it complete."
        if ($copied -gt 0) { Commit-And-Push "partial final artifacts" }
    }
}

try {
    Log "INVERTED_CHECKPOINT_PUBLISHER starting run=$RunId checkpoint=$Checkpoint"
    Ensure-StagingRepo
    New-Item -ItemType Directory -Force -Path $ResultRoot | Out-Null

    $script:LastPublished = 0
    if (Test-Path $ProgressPath) {
        try {
            $existing = Get-Content $ProgressPath -Raw | ConvertFrom-Json
            $script:LastPublished = [int]$existing.completed
            Log "Resume detected: staging progress already contains $script:LastPublished rows."
        } catch {
            Log "Could not parse existing progress.json; rebuilding from local checkpoint. $($_.Exception.Message)"
        }
    }

    $lastPublish = [DateTime]::UtcNow.AddSeconds(-$PublishEverySeconds)
    while ($true) {
        $finalReady = Test-FinalArtifactsReady
        $stop = (Test-Path $StopSignal) -or $finalReady
        $elapsed = ([DateTime]::UtcNow - $lastPublish).TotalSeconds
        if ($stop -or $elapsed -ge $PublishEverySeconds) {
            try {
                Publish-Checkpoint -ForceFinal:$stop
            } catch {
                Log "CHECKPOINT PUBLISH FAILED: $($_.Exception.Message)"
            }
            $lastPublish = [DateTime]::UtcNow
        }
        if ($stop) {
            try { Publish-FinalArtifacts } catch { Log "FINAL PUBLISH FAILED: $($_.Exception.Message)" }
            break
        }
        Start-Sleep -Seconds $PollSeconds
    }
    Log "INVERTED_CHECKPOINT_PUBLISHER stopped. Local checkpoint preserved: $Checkpoint"
} catch {
    Log "INVERTED_CHECKPOINT_PUBLISHER FATAL: $($_.Exception.Message)"
    exit 0
}
