Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Helper = Join-Path $RepoRoot "scripts\invoke-black-magic-native.ps1"
if (-not (Test-Path $Helper)) {
    throw "Expected native capture helper is missing: $Helper"
}
. $Helper

$Root = Join-Path ([System.IO.Path]::GetTempPath()) ("harvest-a-native-stderr-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$LogPath = Join-Path $Root "native.log"

try {
    $args = @(
        "/d",
        "/s",
        "/c",
        "echo Traceback_TEST 1>&2 & echo second_error_line 1>&2 & exit /b 7"
    )
    $exitCode = Invoke-BlackMagicNative -Executable $env:ComSpec -ArgumentList $args -LogPath $LogPath
    if ($exitCode -ne 7) {
        throw "Expected native exit code 7, got $exitCode"
    }
    $text = Get-Content $LogPath -Raw
    if ($text -notmatch "Traceback_TEST") {
        throw "Captured log is missing first stderr line"
    }
    if ($text -notmatch "second_error_line") {
        throw "Captured log is missing later stderr output"
    }
    Write-Host "HARVEST_A_NATIVE_STDERR_CAPTURE_OK"
}
finally {
    Remove-Item -Recurse -Force $Root -ErrorAction SilentlyContinue
}
