$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $RepoRoot "run-harvest-a.ps1"
$Watcher = Join-Path $RepoRoot "scripts\watch-s2-then-harvest.ps1"
$GitIgnore = Join-Path $RepoRoot ".gitignore"

$launcherText = Get-Content $Launcher -Raw
if ($launcherText -notmatch '\[switch\]\$ThenHarvestB') {
    throw "Harvest A launcher does not expose -ThenHarvestB"
}
if ($launcherText -notmatch 'inverted\.black_magic\.epistemic_cli') {
    throw "Harvest A launcher does not invoke Harvest B epistemic CLI"
}
if ($launcherText -notmatch 'black-magic-harvest-b-local\.yaml') {
    throw "Harvest A launcher does not use the real Harvest B config"
}
if ($launcherText -notmatch 'Assert-HarvestCompletionPacket') {
    throw "Harvest A launcher does not gate A/B completion evidence"
}

if (-not (Test-Path $Watcher)) {
    throw "Missing S2 handoff watcher: $Watcher"
}
$watcherText = Get-Content $Watcher -Raw
foreach ($required in @(
    'Assert-S2CompletionPacket',
    'test3-s2-results\\tier-a',
    'tier-a-real',
    'build/black-magic-evidence-tests',
    'ThenHarvestB'
)) {
    if ($watcherText -notmatch $required) {
        throw "S2 handoff watcher is missing contract token: $required"
    }
}

$waitPos = $watcherText.IndexOf('WaitForS2')
$switchPos = $watcherText.IndexOf('git switch')
if ($waitPos -lt 0 -or $switchPos -lt 0 -or $switchPos -lt $waitPos) {
    throw "Watcher must wait for S2 before switching branches"
}

$ignoreText = Get-Content $GitIgnore -Raw
if ($ignoreText -notmatch '(?m)^test3-s2-results/\r?$') {
    throw ".gitignore must ignore S2 evidence after handoff"
}

Write-Host "BLACK_MAGIC_CHAIN_CONTRACT_OK"
