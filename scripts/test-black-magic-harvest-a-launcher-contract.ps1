$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $RepoRoot "run-harvest-a.ps1"
$Publisher = Join-Path $RepoRoot "scripts\publish-black-magic-harvest-a.ps1"
$Cli = Join-Path $RepoRoot "src\inverted\black_magic\cli.py"

$launcherText = Get-Content $Launcher -Raw
$publisherText = Get-Content $Publisher -Raw
$cliText = Get-Content $Cli -Raw

if ($launcherText -match '"--real"') {
    throw "launcher passes unsupported --real flag"
}
if ($cliText -match 'add_argument\("--real"') {
    throw "test assumption changed: CLI now defines --real; review launcher contract"
}

$requiredPublisherArgs = @(
    '-RepoPath',
    '-EvidenceRoot',
    '-StagingRoot',
    '-RunId',
    '-CodeSha',
    '-StopSignal'
)
foreach ($arg in $requiredPublisherArgs) {
    if ($launcherText -notmatch [regex]::Escape('"' + $arg + '"')) {
        throw "launcher is missing publisher argument $arg"
    }
    if ($publisherText -notmatch [regex]::Escape($arg.TrimStart('-'))) {
        throw "publisher does not expose expected parameter $arg"
    }
}

$obsoletePublisherArgs = @('-SourceDir', '-SourceSha', '-StopFile', '-ObserverRoot')
foreach ($arg in $obsoletePublisherArgs) {
    if ($launcherText -match [regex]::Escape('"' + $arg + '"')) {
        throw "launcher still uses obsolete publisher argument $arg"
    }
}

Write-Host "BLACK_MAGIC_HARVEST_A_LAUNCHER_CONTRACT_OK"
