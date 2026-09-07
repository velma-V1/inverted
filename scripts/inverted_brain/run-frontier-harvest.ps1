param(
    [string]$Config = "configs/inverted_brain/frontier_harvest.yaml",
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [switch]$Preflight,
    [switch]$InstrumentSmoke,
    [switch]$Live,
    [switch]$NoResume
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$env:PYTHONPATH = Join-Path $RepoRoot "src"
$Python = if ($env:INVERTED_PYTHON) { $env:INVERTED_PYTHON } else { (Get-Command python -ErrorAction Stop).Source }
$ConfigPath = if ([IO.Path]::IsPathRooted($Config)) { $Config } else { Join-Path $RepoRoot $Config }
$OutputPath = if ([IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $RepoRoot $OutputDir }

$CliArgs = @("-m", "inverted_brain.cli", "--config", $ConfigPath, "--output-dir", $OutputPath)
if ($Preflight) { $CliArgs += "--preflight" }
if ($InstrumentSmoke) { $CliArgs += "--instrument-smoke" }
if ($Live) { $CliArgs += "--live" }
if ($NoResume) { $CliArgs += "--no-resume" }

Write-Host "Inverted Brain runner"
Write-Host "Repo: $RepoRoot"
Write-Host "Python: $Python"
Write-Host "Output: $OutputPath"
& $Python @CliArgs
exit $LASTEXITCODE
