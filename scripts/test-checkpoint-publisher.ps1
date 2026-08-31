$ErrorActionPreference = "Stop"

$Root = Join-Path $env:TEMP ("inverted-publisher-test-" + [Guid]::NewGuid().ToString("N"))
$Bare = Join-Path $Root "remote.git"
$Repo = Join-Path $Root "repo"
$RunRoot = Join-Path $Root "runs"
$RunId = "publisher-test"
$ResultBranch = "results/$RunId"
$Checkpoint = Join-Path $RunRoot "$RunId.checkpoint.jsonl"
$FailureLog = Join-Path $RunRoot "$RunId.call-failures.jsonl"
$FinalRunDir = Join-Path $RunRoot $RunId
$StopSignal = Join-Path $RunRoot "stop.signal"
$Publisher = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\publish-inverted-checkpoints.ps1"

try {
    New-Item -ItemType Directory -Force -Path $Root, $RunRoot, $FinalRunDir | Out-Null
    & git init --bare $Bare | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git init --bare failed" }
    & git clone $Bare $Repo | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
    & git -C $Repo checkout -b main | Out-Null
    Set-Content -Path (Join-Path $Repo "README.md") -Value "publisher integration fixture" -Encoding UTF8
    & git -C $Repo add README.md
    & git -C $Repo -c user.name="ci" -c user.email="ci@example.invalid" commit -m "fixture" | Out-Null
    & git -C $Repo push -u origin main | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "fixture push failed" }

    @('{"trial_id":"t1","run_id":"publisher-test"}','{"trial_id":"t2","run_id":"publisher-test"}') | Set-Content -Path $Checkpoint -Encoding UTF8
    '{"error_class":"GENERATION_CENSORED","output_tokens":1024,"finish_reason":"length"}' | Set-Content -Path $FailureLog -Encoding UTF8

    $RequiredArtifacts = @("events.jsonl","model_calls.jsonl","trials.csv","trials.jsonl","failures.csv","summary.json","summary.csv","report.txt","config.json","provenance.json")
    foreach ($name in $RequiredArtifacts) { Set-Content -Path (Join-Path $FinalRunDir $name) -Value "fixture:$name" -Encoding UTF8 }
    New-Item -ItemType File -Force -Path $StopSignal | Out-Null

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Publisher -RepoPath $Repo -RunRoot $RunRoot -RunId $RunId -Checkpoint $Checkpoint -StopSignal $StopSignal -FinalRunDir $FinalRunDir -TotalTrials 2 -PublishEverySeconds 0 -PollSeconds 1
    if ($LASTEXITCODE -ne 0) { throw "publisher process exited $LASTEXITCODE" }
    & git --git-dir=$Bare show-ref --verify "refs/heads/$ResultBranch" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "results branch was not pushed" }

    $tree = (& git --git-dir=$Bare ls-tree -r --name-only "refs/heads/$ResultBranch" | Out-String)
    $expected = @("live-results/$RunId/chunks/checkpoint-000001-000002.jsonl","live-results/$RunId/progress.json","live-results/$RunId/call-failures.jsonl","live-results/$RunId/final/report.txt","live-results/$RunId/final/provenance.json")
    foreach ($path in $expected) { if ($tree -notmatch [regex]::Escape($path)) { throw "remote branch missing $path" } }
    if (-not (Test-Path $Checkpoint)) { throw "publisher deleted local checkpoint" }
    if (@(Get-Content $Checkpoint).Count -ne 2) { throw "publisher mutated local checkpoint" }
    if (@(Get-Content $FailureLog).Count -ne 1) { throw "publisher mutated local failure log" }
    Write-Host "CHECKPOINT_PUBLISHER_INTEGRATION_OK"
} finally {
    if (Test-Path $Root) { Start-Sleep -Milliseconds 100; Remove-Item $Root -Recurse -Force -ErrorAction SilentlyContinue }
}
