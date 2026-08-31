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
$Branch = "results/$RunId"
$Worktree = Join-Path $RunRoot "$RunId-github"
$ResultRoot = Join-Path $Worktree "live-results\$RunId"
$ChunkRoot = Join-Path $ResultRoot "chunks"
$ProgressPath = Join-Path $ResultRoot "progress.json"
$PublisherLog = Join-Path $RunRoot "$RunId-github-publisher.log"
$RequiredArtifacts = @(
    "events.jsonl",
    "model_calls.jsonl",
    "trials.csv",
    "trials.jsonl",
    "failures.csv",
    "summary.json",
    "summary.csv",
    "report.txt",
    "config.json",
    "provenance.json"
)

function Log([string]$Message) {
    $line = "[$([DateTime]::UtcNow.ToString('o'))] $Message"
    $line | Tee-Object -FilePath $PublisherLog -Append
}

function Get-LineCount([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $count = 0
    $reader = [System.IO.File]::OpenText($Path)
    try {
        while ($null -ne $reader.ReadLine()) { $count++ }
    } finally {
        $reader.Dispose()
    }
    return $count
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

function Ensure-PublishWorktree {
    if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
        throw "INVERTED_REPO_NOT_FOUND:$RepoPath"
    }

    if (Test-Path $Worktree) {
        if (Test-Path (Join-Path $Worktree ".git")) {
            Log "Reusing checkpoint worktree: $Worktree"
            return
        }
        Remove-Item $Worktree -Recurse -Force
    }

    & git -C $RepoPath fetch origin main 2>&1 | ForEach-Object { Log "git fetch: $_" }
    if ($LASTEXITCODE -ne 0) { throw "GIT_FETCH_MAIN_FAILED:$LASTEXITCODE" }

    $remote = (& git -C $RepoPath ls-remote --heads origin "refs/heads/$Branch" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "GIT_LS_REMOTE_FAILED:$LASTEXITCODE" }

    if ($remote) {
        & git -C $RepoPath fetch origin "$Branch`:$Branch" 2>&1 | ForEach-Object { Log "git fetch results: $_" }
        if ($LASTEXITCODE -ne 0) { throw "GIT_FETCH_RESULTS_BRANCH_FAILED:$LASTEXITCODE" }
        & git -C $RepoPath worktree add -B $Branch $Worktree $Branch 2>&1 | ForEach-Object { Log "git worktree: $_" }
    } else {
        & git -C $RepoPath worktree add -b $Branch $Worktree origin/main 2>&1 | ForEach-Object { Log "git worktree: $_" }
    }
    if ($LASTEXITCODE -ne 0) { throw "GIT_WORKTREE_ADD_FAILED:$LASTEXITCODE" }
}

function Commit-And-Push([string]$Reason) {
    & git -C $Worktree add -- "live-results/$RunId"
    if ($LASTEXITCODE -ne 0) { throw "GIT_ADD_CHECKPOINT_FAILED:$LASTEXITCODE" }

    & git -C $Worktree diff --cached --quiet
    $hasChanges = ($LASTEXITCODE -ne 0)
    if ($hasChanges) {
        & git -C $Worktree -c user.name="inverted-checkpoint" -c user.email="inverted-checkpoint@users.noreply.github.com" commit -m "results: $RunId $Reason" 2>&1 | ForEach-Object { Log "git commit: $_" }
        if ($LASTEXITCODE -ne 0) { throw "GIT_COMMIT_CHECKPOINT_FAILED:$LASTEXITCODE" }
    }

    & git -C $Worktree push origin "HEAD:refs/heads/$Branch" 2>&1 | ForEach-Object { Log "git push: $_" }
    if ($LASTEXITCODE -ne 0) { throw "GIT_PUSH_CHECKPOINT_FAILED:$LASTEXITCODE" }
    Log "REMOTE CHECKPOINT VERIFIED branch=$Branch reason=$Reason"
}

function Publish-Checkpoint([bool]$ForceFinal = $false) {
    $completed = Get-LineCount $Checkpoint
    if ($completed -le $script:LastPublished) { return }

    New-Item -ItemType Directory -Force -Path $ChunkRoot | Out-Null
    $start = $script:LastPublished + 1
    $end = $completed
    $chunkName = "checkpoint-{0:D6}-{1:D6}.jsonl" -f $start, $end
    $chunkPath = Join-Path $ChunkRoot $chunkName
    Write-CheckpointChunk $Checkpoint $start $end $chunkPath
    $hash = (Get-FileHash -Algorithm SHA256 -Path $chunkPath).Hash

    $progress = [ordered]@{
        run_id = $RunId
        branch = $Branch
        completed = $completed
        total = $TotalTrials
        percent = if ($TotalTrials -gt 0) { [Math]::Round(100.0 * $completed / $TotalTrials, 4) } else { 100.0 }
        last_chunk = $chunkName
        last_chunk_sha256 = $hash
        updated_utc = [DateTime]::UtcNow.ToString("o")
        final_signal_seen = $ForceFinal
        local_checkpoint = $Checkpoint
    }
    $progress | ConvertTo-Json -Depth 6 | Set-Content -Path $ProgressPath -Encoding UTF8

    Commit-And-Push "checkpoint $start-$end"
    $script:LastPublished = $completed
    Log "Published checkpoint rows $start-$end SHA256=$hash"
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
        if ($copied -gt 0) {
            Commit-And-Push "partial final artifacts"
        }
    }
}

try {
    Log "INVERTED_CHECKPOINT_PUBLISHER starting run=$RunId checkpoint=$Checkpoint"
    Ensure-PublishWorktree
    New-Item -ItemType Directory -Force -Path $ResultRoot | Out-Null

    $script:LastPublished = 0
    if (Test-Path $ProgressPath) {
        try {
            $existing = Get-Content $ProgressPath -Raw | ConvertFrom-Json
            $script:LastPublished = [int]$existing.completed
            Log "Resume detected: remote progress already contains $script:LastPublished rows."
        } catch {
            Log "Could not parse existing progress.json; rebuilding from chunks. $($_.Exception.Message)"
        }
    }

    $lastPublish = [DateTime]::UtcNow.AddSeconds(-$PublishEverySeconds)
    while ($true) {
        $stop = Test-Path $StopSignal
        $elapsed = ([DateTime]::UtcNow - $lastPublish).TotalSeconds
        if ($stop -or $elapsed -ge $PublishEverySeconds) {
            try {
                Publish-Checkpoint -ForceFinal:$stop
            } catch {
                # Remote publication is explicitly non-blocking. Local checkpoint
                # remains untouched and the next cycle retries the accumulated commits.
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
    # Never delete or mutate the local checkpoint; publisher failure must not
    # stop or contaminate the benchmark itself.
    exit 0
}
