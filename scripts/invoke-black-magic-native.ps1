function Invoke-BlackMagicNative {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Executable @ArgumentList 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Host $line
            Add-Content -Path $LogPath -Value $line -Encoding UTF8
        }
        $nativeExitCode = [int]$LASTEXITCODE
        $global:LASTEXITCODE = 0
        return $nativeExitCode
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}
