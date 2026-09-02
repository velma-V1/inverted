$ErrorActionPreference = "Stop"

$Root = Join-Path $env:TEMP ("black-magic-harvest-a-publisher-test-" + [Guid]::NewGuid().ToString("N"))
$Bare = Join-Path $Root "remote.git"
$Repo = Join-Path $Root "repo"
$EvidenceRoot = Join-Path $Root "evidence"
$StagingRoot = Join-Path $Root "staging"
$RunId = "publisher-test"
$CodeSha = $null
$StopSignal = Join-Path $Root "stop.signal"
$Publisher = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts\publish-black-magic-harvest-a.ps1"
$RemoteBranch = "evidence/harvest-a-$RunId"

try {
    New-Item -ItemType Directory -Force -Path $Root, $EvidenceRoot, $StagingRoot | Out-Null
    & git init --bare $Bare | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git init --bare failed" }
    & git clone $Bare $Repo | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
    & git -C $Repo checkout -b main | Out-Null
    Set-Content -Path (Join-Path $Repo "README.md") -Value "harvest-a publisher fixture" -Encoding UTF8
    & git -C $Repo add README.md
    & git -C $Repo -c user.name="ci" -c user.email="ci@example.invalid" commit -m "fixture" | Out-Null
    & git -C $Repo push -u origin main | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "fixture push failed" }
    $CodeSha = (& git -C $Repo rev-parse HEAD).Trim()

    @(
        '{"external_action_id":"a1","run_id":"publisher-test"}',
        '{"external_action_id":"a2","run_id":"publisher-test"}',
        '{"external_action_id":"a3","run_id":"publisher-test"}'
    ) | Set-Content -Path (Join-Path $EvidenceRoot "external_actions.jsonl") -Encoding UTF8
    '{"event_type":"run_started"}' | Set-Content -Path (Join-Path $EvidenceRoot "events.jsonl") -Encoding UTF8
    '{"status":"OK"}' | Set-Content -Path (Join-Path $EvidenceRoot "integrity.json") -Encoding UTF8
    '{"used":3,"cap":1200}' | Set-Content -Path (Join-Path $EvidenceRoot "budget.json") -Encoding UTF8
    "path,bytes,sha256`nintegrity.json,16,fixture" | Set-Content -Path (Join-Path $EvidenceRoot "SHA256SUMS.csv") -Encoding UTF8

    $beforeHash = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $EvidenceRoot "external_actions.jsonl")).Hash
    New-Item -ItemType File -Force -Path $StopSignal | Out-Null

    if (-not (Test-Path $Publisher)) { throw "HARVEST_A_PUBLISHER_MISSING:$Publisher" }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Publisher `
        -RepoPath $Repo `
        -EvidenceRoot $EvidenceRoot `
        -StagingRoot $StagingRoot `
        -RunId $RunId `
        -CodeSha $CodeSha `
        -StopSignal $StopSignal `
        -TotalActions 1200 `
        -PublishEveryActions 2 `
        -PublishEverySeconds 0 `
        -PollSeconds 1
    if ($LASTEXITCODE -ne 0) { throw "publisher process exited $LASTEXITCODE" }

    & git --git-dir=$Bare show-ref --verify "refs/heads/$RemoteBranch" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "evidence branch was not pushed" }

    $tree = (& git --git-dir=$Bare ls-tree -r --name-only "refs/heads/$RemoteBranch" | Out-String)
    $expected = @(
        "live-evidence/harvest-a/$RunId/current/external_actions.jsonl",
        "live-evidence/harvest-a/$RunId/current/integrity.json",
        "live-evidence/harvest-a/$RunId/progress.json"
    )
    foreach ($path in $expected) {
        if ($tree -notmatch [regex]::Escape($path)) { throw "remote evidence branch missing $path" }
    }

    $afterHash = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $EvidenceRoot "external_actions.jsonl")).Hash
    if ($beforeHash -ne $afterHash) { throw "publisher mutated local evidence" }

    $repoHead = (& git -C $Repo rev-parse HEAD).Trim()
    if ($repoHead -ne $CodeSha) { throw "publisher moved source repository HEAD" }
    $repoBranch = (& git -C $Repo branch --show-current).Trim()
    if ($repoBranch -ne "main") { throw "publisher switched source repository branch" }

    Write-Host "BLACK_MAGIC_HARVEST_A_PUBLISHER_INTEGRATION_OK"
} finally {
    if (Test-Path $Root) {
        Start-Sleep -Milliseconds 100
        Remove-Item $Root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
