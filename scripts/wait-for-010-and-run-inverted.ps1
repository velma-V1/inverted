param(
    [string]$ProcessPattern = "alien",
    [string]$RepoPath = "$HOME\inverted",
    [string]$AlienRepoPath = "",
    [string]$AlienBranch = "experiment/010-computational-basis-atlas",
    [string]$PythonExe = "C:\Python314\python.exe",
    [string]$Model1 = "qwen3.5:9b-q8_0",
    [string]$Model2 = "gemma3:12b",
    [string]$Model3 = "devstral-small-2:24b",
    [string]$RunRoot = "$HOME\inverted-runs"
)

$ErrorActionPreference = "Stop"
$script:Last010CommandLine = $null
$script:Last010OutputArg = $null

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " HANDOFF STOPPED" -ForegroundColor Red
    Write-Host " $Message" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    throw $Message
}

function Get-010Processes {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(\.exe)?$' -and
        $_.CommandLine -and
        $_.CommandLine -match $ProcessPattern
    })
}

function Capture-010CommandLine([object[]]$Matches) {
    if (-not $Matches -or $Matches.Count -eq 0) { return }
    $line = [string]$Matches[0].CommandLine
    if (-not $line) { return }
    $script:Last010CommandLine = $line

    $match = [regex]::Match($line, '--output-dir(?:=|\s+)(?:"([^"]+)"|''([^'']+)''|([^\s]+))')
    if ($match.Success) {
        foreach ($index in 1..3) {
            if ($match.Groups[$index].Success) {
                $script:Last010OutputArg = $match.Groups[$index].Value
                break
            }
        }
    }
}

function Find-AlienRepo {
    if ($AlienRepoPath -and (Test-Path (Join-Path $AlienRepoPath ".git"))) {
        return (Resolve-Path $AlienRepoPath).Path
    }

    $candidates = @(
        "$HOME\Documents\GitHub\velma-alien-stack-lab",
        "$HOME\GitHub\velma-alien-stack-lab",
        "$HOME\velma-alien-stack-lab",
        "$HOME\source\repos\velma-alien-stack-lab"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate ".git")) {
            return (Resolve-Path $candidate).Path
        }
    }

    try {
        $found = Get-ChildItem -Path $HOME -Directory -Filter "velma-alien-stack-lab" -Recurse -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName ".git") } |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    } catch {
        Write-Host "Alien repo discovery warning: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    return $null
}

function Resolve-010OutputDir([string]$AlienRepo) {
    if ($script:Last010OutputArg) {
        if ([System.IO.Path]::IsPathRooted($script:Last010OutputArg)) {
            if (Test-Path $script:Last010OutputArg) {
                return (Resolve-Path $script:Last010OutputArg).Path
            }
        } elseif ($AlienRepo) {
            $candidate = Join-Path $AlienRepo $script:Last010OutputArg
            if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
        }
    }

    if ($AlienRepo) {
        $summary = Get-ChildItem -Path $AlienRepo -Filter "live-summary.json" -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($summary) { return $summary.Directory.FullName }

        $manifest = Get-ChildItem -Path $AlienRepo -Filter "live-manifest.json" -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($manifest) { return $manifest.Directory.FullName }
    }
    return $null
}

function Write-CommandOutput([string]$Title, [scriptblock]$Command) {
    Write-Host ""
    Write-Host "----- $Title -----" -ForegroundColor Cyan
    try {
        & $Command 2>&1 | ForEach-Object { Write-Host $_ }
    } catch {
        Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Dump-010Evidence([string]$AlienRepo, [string]$OutputDir, [string]$PushLog) {
    Write-Host ""
    Write-Host "################################################################" -ForegroundColor Yellow
    Write-Host " 010 PUSH FAILED - PRINTING ALL AVAILABLE LOCAL INFORMATION/DATA" -ForegroundColor Yellow
    Write-Host "################################################################" -ForegroundColor Yellow
    Write-Host "Captured 010 command line: $script:Last010CommandLine"
    Write-Host "Captured --output-dir: $script:Last010OutputArg"
    Write-Host "Resolved Alien repo: $AlienRepo"
    Write-Host "Resolved 010 output: $OutputDir"
    Write-Host "Target branch: $AlienBranch"

    if ($PushLog -and (Test-Path $PushLog)) {
        Write-Host ""
        Write-Host "----- GIT PUSH OUTPUT -----" -ForegroundColor Cyan
        Get-Content -Path $PushLog -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    }

    if ($AlienRepo -and (Test-Path (Join-Path $AlienRepo ".git"))) {
        Write-CommandOutput "git status --short --branch" { git -C $AlienRepo status --short --branch }
        Write-CommandOutput "git branch --show-current" { git -C $AlienRepo branch --show-current }
        Write-CommandOutput "git remote -v" { git -C $AlienRepo remote -v }
        Write-CommandOutput "git log -10 --oneline --decorate" { git -C $AlienRepo log -10 --oneline --decorate }
        Write-CommandOutput "git diff --stat" { git -C $AlienRepo diff --stat }
        Write-CommandOutput "git diff --cached --stat" { git -C $AlienRepo diff --cached --stat }
        Write-CommandOutput "git diff" { git -C $AlienRepo diff }
        Write-CommandOutput "git diff --cached" { git -C $AlienRepo diff --cached }
        Write-CommandOutput "remote 010 branch SHA" { git -C $AlienRepo ls-remote origin "refs/heads/$AlienBranch" }
    }

    if ($OutputDir -and (Test-Path $OutputDir)) {
        Write-Host ""
        Write-Host "----- 010 RESULT FILE INVENTORY -----" -ForegroundColor Cyan
        $files = @(Get-ChildItem -Path $OutputDir -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName)
        Write-Host "Result files: $($files.Count)"

        $textExtensions = @(".json", ".jsonl", ".csv", ".txt", ".md", ".log", ".yaml", ".yml", ".toml")
        foreach ($file in $files) {
            $hash = "UNAVAILABLE"
            try { $hash = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash } catch {}
            Write-Host ""
            Write-Host "===== FILE: $($file.FullName) =====" -ForegroundColor DarkCyan
            Write-Host "SIZE_BYTES=$($file.Length) LAST_WRITE_UTC=$($file.LastWriteTimeUtc.ToString('o')) SHA256=$hash"
            if ($textExtensions -contains $file.Extension.ToLowerInvariant()) {
                try {
                    Get-Content -Path $file.FullName -Raw -ErrorAction Stop | Write-Host
                } catch {
                    Write-Host "TEXT_READ_ERROR: $($_.Exception.Message)" -ForegroundColor Yellow
                }
            } else {
                Write-Host "NON_TEXT_FILE_CONTENT_NOT_RENDERED; metadata/hash preserved above."
            }
        }
    } else {
        Write-Host "No 010 output directory could be resolved; no result files can be rendered." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "################################################################" -ForegroundColor Yellow
    Write-Host " END 010 FAILURE DUMP - INVERTED WILL STILL START" -ForegroundColor Yellow
    Write-Host "################################################################" -ForegroundColor Yellow
}

function Publish-010Results {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " PUBLISHING COMPLETE 010 LIVE C/D RESULTS"
    Write-Host "============================================================"

    $alienRepo = Find-AlienRepo
    $outputDir = Resolve-010OutputDir $alienRepo
    $pushLog = Join-Path $RunRoot "010-git-push-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    $publishSucceeded = $false

    try {
        if (-not $alienRepo) { throw "LOCAL_ALIEN_REPO_NOT_FOUND" }
        if (-not $outputDir) { throw "010_OUTPUT_DIRECTORY_NOT_FOUND" }
        if (-not (Test-Path (Join-Path $outputDir "live-manifest.json"))) { throw "LIVE_MANIFEST_MISSING:$outputDir" }
        if (-not (Test-Path (Join-Path $outputDir "live-summary.json"))) { throw "LIVE_SUMMARY_MISSING:$outputDir" }

        $branch = (& git -C $alienRepo branch --show-current 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "GIT_BRANCH_READ_FAILED:$LASTEXITCODE" }
        if ($branch -ne $AlienBranch) {
            Write-Host "Switching Alien Labs checkout from '$branch' to '$AlienBranch'..."
            & git -C $alienRepo checkout $AlienBranch
            if ($LASTEXITCODE -ne 0) { throw "GIT_CHECKOUT_010_BRANCH_FAILED:$LASTEXITCODE" }
        }

        $repoFull = [System.IO.Path]::GetFullPath($alienRepo).TrimEnd('\', '/')
        $outputFull = [System.IO.Path]::GetFullPath($outputDir).TrimEnd('\', '/')
        $stagePath = $null

        if ($outputFull.StartsWith($repoFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            $stagePath = $outputFull.Substring($repoFull.Length).TrimStart('\', '/')
        } else {
            $destination = Join-Path $alienRepo ("results\010-live-cd-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
            Write-Host "010 output is outside repo; copying complete bundle to $destination"
            Copy-Item -Path $outputDir -Destination $destination -Recurse -Force
            $stagePath = [System.IO.Path]::GetFullPath($destination).Substring($repoFull.Length).TrimStart('\', '/')
            $outputDir = $destination
        }

        Write-Host "Staging complete 010 bundle: $stagePath"
        & git -C $alienRepo add -f -- $stagePath
        if ($LASTEXITCODE -ne 0) { throw "GIT_ADD_010_RESULTS_FAILED:$LASTEXITCODE" }

        & git -C $alienRepo diff --cached --quiet -- $stagePath
        $hasStagedChanges = ($LASTEXITCODE -ne 0)
        if ($hasStagedChanges) {
            $commitMessage = "results: capture 010 live C/D $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
            & git -C $alienRepo -c user.name="010-autopush" -c user.email="010-autopush@users.noreply.github.com" commit -m $commitMessage -- $stagePath
            if ($LASTEXITCODE -ne 0) { throw "GIT_COMMIT_010_RESULTS_FAILED:$LASTEXITCODE" }
        } else {
            Write-Host "No new staged 010 result changes; pushing current 010 branch state."
        }

        Write-Host "Pushing 010 results to origin/$AlienBranch..."
        & git -C $alienRepo push origin "HEAD:refs/heads/$AlienBranch" 2>&1 | Tee-Object -FilePath $pushLog
        $pushExit = $LASTEXITCODE
        if ($pushExit -ne 0) { throw "GIT_PUSH_010_RESULTS_FAILED:$pushExit" }

        $localSha = (& git -C $alienRepo rev-parse HEAD 2>&1 | Out-String).Trim()
        $remoteLine = (& git -C $alienRepo ls-remote origin "refs/heads/$AlienBranch" 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "GIT_REMOTE_VERIFY_FAILED:$LASTEXITCODE" }
        $remoteSha = ($remoteLine -split '\s+')[0]
        if (-not $localSha -or $remoteSha -ne $localSha) {
            throw "GIT_PUSH_VERIFY_MISMATCH:local=$localSha:remote=$remoteSha"
        }

        $publishSucceeded = $true
        Write-Host ""
        Write-Host "010 RESULTS PUSH VERIFIED" -ForegroundColor Green
        Write-Host "Repository: $alienRepo"
        Write-Host "Branch: $AlienBranch"
        Write-Host "Commit: $localSha"
        Write-Host "Result bundle: $outputDir"
    } catch {
        Write-Host ""
        Write-Host "010 RESULTS PUSH FAILED: $($_.Exception.Message)" -ForegroundColor Yellow
        Dump-010Evidence $alienRepo $outputDir $pushLog
    }

    return $publishSucceeded
}

New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$StateFile = Join-Path $RunRoot "active-run-id.txt"
$ResumeExisting = Test-Path $StateFile

# Keep the computer awake while plugged in. Display timeout is unaffected.
powercfg /change standby-timeout-ac 0

if (-not $ResumeExisting) {
    Write-Host "============================================================"
    Write-Host " WAITING FOR 010 LIVE C/D TEST"
    Write-Host " Process pattern: $ProcessPattern"
    Write-Host "============================================================"

    $Seen010 = $false
    $ClearChecks = 0
    $WaitStart = Get-Date

    while ($true) {
        $Matches = Get-010Processes
        if ($Matches.Count -gt 0) {
            $Seen010 = $true
            $ClearChecks = 0
            Capture-010CommandLine $Matches
            $Elapsed = (Get-Date) - $WaitStart
            $Pids = ($Matches | ForEach-Object { $_.ProcessId }) -join ","
            $status = "Elapsed {0:hh\:mm\:ss} | PID(s): {1}" -f $Elapsed, $Pids
            if ($script:Last010OutputArg) { $status += " | Output: $script:Last010OutputArg" }
            Write-Progress -Id 1 -Activity "010 LIVE C/D TEST RUNNING" -Status $status
            Start-Sleep -Seconds 10
            continue
        }

        if (-not $Seen010) {
            Write-Progress -Id 1 -Activity "010 watcher" -Completed
            Fail "No running 010 process matched '$ProcessPattern'; refusing to start a fresh handoff because 010 was never observed."
        }

        $ClearChecks++
        Write-Progress -Id 1 -Activity "VERIFYING 010 HAS FINISHED" -Status "No match: confirmation $ClearChecks of 3"
        if ($ClearChecks -ge 3) { break }
        Start-Sleep -Seconds 10
    }

    Write-Progress -Id 1 -Activity "010 watcher" -Completed
    Write-Host "010 process has remained absent for three consecutive checks."

    # Publication is best-effort. Failure dumps all recoverable local evidence but does NOT block inverted.
    $010PublishSucceeded = Publish-010Results
    if (-not $010PublishSucceeded) {
        Write-Host "010 publication did not verify. Continuing to inverted by explicit policy." -ForegroundColor Yellow
    }
} else {
    Write-Host "Existing inverted run state found. Resuming run ID: $(Get-Content $StateFile -Raw)"
}

Write-Host ""
Write-Host "============================================================"
Write-Host " PREPARING INVERTED BENCHMARK"
Write-Host "============================================================"

if (-not (Test-Path $PythonExe)) { Fail "Python executable not found: $PythonExe" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git is not available on PATH." }

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    Write-Host "Cloning velma-V1/inverted..."
    & git clone "https://github.com/velma-V1/inverted.git" $RepoPath
    if ($LASTEXITCODE -ne 0) { Fail "git clone failed with exit code $LASTEXITCODE" }
}

& git -C $RepoPath checkout main
if ($LASTEXITCODE -ne 0) { Fail "git checkout main failed with exit code $LASTEXITCODE" }
& git -C $RepoPath pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { Fail "git pull failed with exit code $LASTEXITCODE" }

$ConfigPath = Join-Path $RepoPath "configs\decisive.yaml"
$CliPath = Join-Path $RepoPath "src\inverted\cli.py"
if (-not (Test-Path $ConfigPath)) { Fail "Missing decisive config: $ConfigPath" }
if (-not (Test-Path $CliPath)) { Fail "Missing benchmark package: $CliPath" }

Write-Host "Installing/verifying benchmark package..."
& $PythonExe -m pip install -e $RepoPath
if ($LASTEXITCODE -ne 0) { Fail "Benchmark installation failed with exit code $LASTEXITCODE" }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { Fail "Ollama is not available on PATH." }

Write-Host "Checking Ollama models..."
$OllamaList = (& ollama list 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { Fail "ollama list failed with exit code $LASTEXITCODE" }

$RequiredModels = @($Model1, $Model2, $Model3)
foreach ($Model in $RequiredModels) {
    if ($OllamaList -notmatch [regex]::Escape($Model)) { Fail "Required Ollama model missing: $Model" }
    Write-Host "  OK: $Model"
}

$env:INVERTED_MODEL_1 = $Model1
$env:INVERTED_MODEL_2 = $Model2
$env:INVERTED_MODEL_3 = $Model3

if ($ResumeExisting) {
    $RunId = (Get-Content $StateFile -Raw).Trim()
    if (-not $RunId) { Fail "Existing active-run-id.txt is empty." }
} else {
    $RunId = "decisive-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Set-Content -Path $StateFile -Value $RunId -Encoding UTF8
}

$Checkpoint = Join-Path $RunRoot "$RunId.checkpoint.jsonl"
$TerminalLog = Join-Path $RunRoot "$RunId-terminal.log"
$RunDir = Join-Path $RunRoot $RunId

Write-Host ""
Write-Host "============================================================"
Write-Host " STARTING REAL-MODEL INVERTED BENCHMARK"
Write-Host " Run ID: $RunId"
Write-Host " Model 1: $Model1"
Write-Host " Model 2: $Model2"
Write-Host " Model 3: $Model3"
Write-Host " Checkpoint: $Checkpoint"
Write-Host "============================================================"

$Start = Get-Date
& $PythonExe -m inverted.cli `
    --config $ConfigPath `
    --output-dir $RunRoot `
    --run-id $RunId `
    --checkpoint $Checkpoint `
    --resume `
    --progress 2>&1 | Tee-Object -FilePath $TerminalLog
$BenchmarkExitCode = $LASTEXITCODE

if ($BenchmarkExitCode -ne 0) {
    Fail "Inverted benchmark failed with exit code $BenchmarkExitCode. Run state and checkpoint were preserved for resume."
}

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

foreach ($Artifact in $RequiredArtifacts) {
    $ArtifactPath = Join-Path $RunDir $Artifact
    if (-not (Test-Path $ArtifactPath)) { Fail "Benchmark exited successfully but required artifact is missing: $ArtifactPath" }
}

$Elapsed = (Get-Date) - $Start
Remove-Item $StateFile -Force

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " INVERTED BENCHMARK COMPLETE" -ForegroundColor Green
Write-Host (" Runtime: {0:hh\:mm\:ss}" -f $Elapsed)
Write-Host " Results: $RunDir"
Write-Host " Terminal log: $TerminalLog"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press ENTER to close"
