$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$Launcher = Join-Path $RepoRoot "run-harvest-a.ps1"
$Publisher = Join-Path $RepoRoot "scripts\publish-black-magic-harvest-a.ps1"
$Cli = Join-Path $RepoRoot "src\inverted\black_magic\cli.py"
$Config = Join-Path $RepoRoot "configs\black-magic-harvest-a-local.yaml"

$launcherText = Get-Content $Launcher -Raw
$publisherText = Get-Content $Publisher -Raw
$cliText = Get-Content $Cli -Raw
$configText = Get-Content $Config -Raw

if ($launcherText -match '"--real"') {
    throw "launcher passes unsupported --real flag"
}
if ($cliText -match 'add_argument\("--real"') {
    throw "test assumption changed: CLI now defines --real; review launcher contract"
}

$publisherMatch = [regex]::Match(
    $launcherText,
    '(?s)\$publisherArgs\s*=\s*@\((.*?)\)\s*\r?\n\$PublisherProcess'
)
if (-not $publisherMatch.Success) {
    throw "could not isolate launcher publisherArgs block"
}
$publisherArgsText = $publisherMatch.Groups[1].Value

$requiredPublisherArgs = @(
    '-RepoPath',
    '-EvidenceRoot',
    '-StagingRoot',
    '-RunId',
    '-CodeSha',
    '-StopSignal'
)
foreach ($arg in $requiredPublisherArgs) {
    if ($publisherArgsText -notmatch [regex]::Escape('"' + $arg + '"')) {
        throw "launcher publisherArgs is missing $arg"
    }
    if ($publisherText -notmatch [regex]::Escape($arg.TrimStart('-'))) {
        throw "publisher does not expose expected parameter $arg"
    }
}

$obsoletePublisherArgs = @('-SourceDir', '-SourceSha', '-StopFile', '-ObserverRoot')
foreach ($arg in $obsoletePublisherArgs) {
    if ($publisherArgsText -match [regex]::Escape('"' + $arg + '"')) {
        throw "launcher publisherArgs still uses obsolete argument $arg"
    }
}

foreach ($index in 1..3) {
    $required = "INVERTED_MODEL_$index"
    if ($configText -notmatch [regex]::Escape('${' + $required + '}')) {
        throw "Harvest A config no longer consumes expected variable $required"
    }
    if ($launcherText -notmatch [regex]::Escape('$env:' + $required)) {
        throw "launcher does not export config variable $required"
    }

    $obsolete = "INVERTED_OLLAMA_MODEL_$index"
    if ($launcherText -match [regex]::Escape('$env:' + $obsolete)) {
        throw "launcher still exports obsolete model variable $obsolete"
    }
}

Write-Host "BLACK_MAGIC_HARVEST_A_LAUNCHER_CONTRACT_OK"
