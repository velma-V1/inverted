$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $RepoRoot 'src'
$Separator = [IO.Path]::PathSeparator
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$Src$Separator$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $Src
}

Push-Location $RepoRoot
try {
    & python -m inverted.qwen_thinking_tuning @args
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $ExitCode
