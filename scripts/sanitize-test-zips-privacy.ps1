param(
    [Parameter(Mandatory = $true)]
    [string[]]$ZipPath,

    [switch]$ReplaceOriginal
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$Replacements = [System.Collections.Generic.Dictionary[string,string]]::new([System.StringComparer]::Ordinal)
$Categories = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)

function Test-MeaningfulIdentifier {
    param([AllowNull()][string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    $v = $Value.Trim()
    if ($v.Length -lt 4) { return $false }
    $lower = $v.ToLowerInvariant()
    $bad = @(
        "none", "unknown", "not specified", "default string", "system serial number",
        "to be filled by o.e.m.", "to be filled by oem", "0123456789",
        "00000000-0000-0000-0000-000000000000", "ffffffff-ffff-ffff-ffff-ffffffffffff"
    )
    if ($bad -contains $lower) { return $false }
    if ($v -match '^[0\-:\s]+$') { return $false }
    return $true
}

function Add-Identifier {
    param(
        [AllowNull()][string]$Value,
        [Parameter(Mandatory = $true)][string]$Placeholder,
        [Parameter(Mandatory = $true)][string]$Category,
        [switch]$CaseVariants,
        [switch]$MacVariants
    )
    if (-not (Test-MeaningfulIdentifier $Value)) { return }
    $valueText = $Value.Trim()
    $values = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    [void]$values.Add($valueText)
    if ($CaseVariants) {
        [void]$values.Add($valueText.ToLowerInvariant())
        [void]$values.Add($valueText.ToUpperInvariant())
    }
    if ($MacVariants) {
        [void]$values.Add($valueText.Replace('-', ':'))
        [void]$values.Add($valueText.Replace(':', '-'))
        [void]$values.Add($valueText.Replace('-', ':').ToLowerInvariant())
        [void]$values.Add($valueText.Replace(':', '-').ToLowerInvariant())
        [void]$values.Add($valueText.Replace('-', ':').ToUpperInvariant())
        [void]$values.Add($valueText.Replace(':', '-').ToUpperInvariant())
    }
    foreach ($candidate in $values) {
        if (-not $Replacements.ContainsKey($candidate)) {
            $Replacements.Add($candidate, $Placeholder)
        }
    }
    [void]$Categories.Add($Category)
}

# Exact local profile paths. The bare username is intentionally NOT redacted because it
# may legitimately occur inside prompts/test content; the absolute profile path is PC-specific.
Add-Identifier -Value $env:USERPROFILE -Placeholder "[REDACTED_USER_PROFILE]" -Category "user_profile_path"
if (-not [string]::IsNullOrWhiteSpace($env:HOMEDRIVE) -and -not [string]::IsNullOrWhiteSpace($env:HOMEPATH)) {
    Add-Identifier -Value ($env:HOMEDRIVE + $env:HOMEPATH) -Placeholder "[REDACTED_USER_PROFILE]" -Category "home_path"
}
Add-Identifier -Value $env:COMPUTERNAME -Placeholder "[REDACTED_HOST]" -Category "hostname" -CaseVariants

try {
    $cv = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Cryptography' -ErrorAction Stop
    Add-Identifier -Value ([string]$cv.MachineGuid) -Placeholder "[REDACTED_MACHINE_GUID]" -Category "machine_guid" -CaseVariants
} catch {}

try {
    $nt = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction Stop
    Add-Identifier -Value ([string]$nt.ProductId) -Placeholder "[REDACTED_WINDOWS_PRODUCT_ID]" -Category "windows_product_id"
} catch {}

try {
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    Add-Identifier -Value ([string]$sid) -Placeholder "[REDACTED_WINDOWS_SID]" -Category "windows_sid"
} catch {}

try {
    $systemProduct = Get-CimInstance -ClassName Win32_ComputerSystemProduct -ErrorAction Stop
    Add-Identifier -Value ([string]$systemProduct.UUID) -Placeholder "[REDACTED_SYSTEM_UUID]" -Category "system_uuid" -CaseVariants
} catch {}

try {
    $bios = Get-CimInstance -ClassName Win32_BIOS -ErrorAction Stop
    Add-Identifier -Value ([string]$bios.SerialNumber) -Placeholder "[REDACTED_BIOS_SERIAL]" -Category "bios_serial"
} catch {}

try {
    $boards = @(Get-CimInstance -ClassName Win32_BaseBoard -ErrorAction Stop)
    foreach ($board in $boards) {
        Add-Identifier -Value ([string]$board.SerialNumber) -Placeholder "[REDACTED_BASEBOARD_SERIAL]" -Category "baseboard_serial"
    }
} catch {}

try {
    $adapters = @(Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration -Filter "IPEnabled=True" -ErrorAction Stop)
    foreach ($adapter in $adapters) {
        Add-Identifier -Value ([string]$adapter.MACAddress) -Placeholder "[REDACTED_MAC]" -Category "mac_address" -MacVariants
    }
} catch {}

try {
    $gitEmail = ((git config --get user.email) | Out-String).Trim()
    if ($LASTEXITCODE -eq 0) {
        Add-Identifier -Value $gitEmail -Placeholder "[REDACTED_GIT_EMAIL]" -Category "git_email" -CaseVariants
    }
} catch {}

if ($Replacements.Count -eq 0) {
    throw "No exact PC/privacy identifiers could be derived. No ZIP was modified."
}

$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("inverted-privacy-scrub-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
$ReplacementFile = Join-Path $TempRoot "replacements.json"
$Replacements | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $ReplacementFile -Encoding UTF8

try {
    Write-Host "Privacy scrub categories detected: $((@($Categories) | Sort-Object) -join ', ')"
    Write-Host "Exact identifier values are intentionally not printed."

    foreach ($requested in $ZipPath) {
        $Source = Get-Item -LiteralPath $requested -ErrorAction Stop
        if ($Source.PSIsContainer -or $Source.Extension -ine '.zip') {
            throw "Privacy scrub accepts explicit ZIP files only."
        }

        $SanitizedName = $Source.BaseName + ".privacy-sanitized-" + [guid]::NewGuid().ToString("N") + ".zip"
        $SanitizedPath = Join-Path $TempRoot $SanitizedName

        $raw = & python -m inverted.harvest_d.privacy_sanitize_test_zip `
            --source $Source.FullName `
            --output $SanitizedPath `
            --replacements-json $ReplacementFile
        if ($LASTEXITCODE -ne 0) {
            throw "Privacy scrub failed closed for '$($Source.Name)'. Original ZIP was not modified."
        }

        $result = ($raw | Out-String).Trim() | ConvertFrom-Json
        if ($result.state -ne 'PRIVACY_SANITIZED' -or [int]$result.remaining_matches -ne 0) {
            throw "Privacy verification did not reach zero remaining exact identifiers for '$($Source.Name)'."
        }

        $SanitizedHash = (Get-FileHash -LiteralPath $SanitizedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($SanitizedHash -ne ([string]$result.output_sha256).ToLowerInvariant()) {
            throw "Sanitized ZIP hash verification failed for '$($Source.Name)'."
        }

        if ($ReplaceOriginal) {
            $OriginalTemp = Join-Path $TempRoot ($Source.Name + ".original")
            Move-Item -LiteralPath $Source.FullName -Destination $OriginalTemp -Force
            try {
                Move-Item -LiteralPath $SanitizedPath -Destination $Source.FullName -Force
                $InstalledHash = (Get-FileHash -LiteralPath $Source.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($InstalledHash -ne $SanitizedHash) {
                    throw "Installed sanitized ZIP hash mismatch."
                }
                Remove-Item -LiteralPath $OriginalTemp -Force
            } catch {
                if (Test-Path -LiteralPath $Source.FullName) {
                    Remove-Item -LiteralPath $Source.FullName -Force -ErrorAction SilentlyContinue
                }
                if (Test-Path -LiteralPath $OriginalTemp) {
                    Move-Item -LiteralPath $OriginalTemp -Destination $Source.FullName -Force
                }
                throw
            }
            Write-Host "PRIVACY_SANITIZED: $($Source.Name)"
        } else {
            $Destination = Join-Path $Source.DirectoryName ($Source.BaseName + ".PRIVACY-SANITIZED.zip")
            if (Test-Path -LiteralPath $Destination) {
                throw "Sanitized destination already exists: $([IO.Path]::GetFileName($Destination))"
            }
            Move-Item -LiteralPath $SanitizedPath -Destination $Destination
            Write-Host "PRIVACY_SANITIZED_COPY: $([IO.Path]::GetFileName($Destination))"
        }

        Write-Host "  changed members: $($result.changed_members)"
        Write-Host "  unchanged members: $($result.unchanged_members)"
        Write-Host "  nested ZIPs: $($result.nested_zips)"
        Write-Host "  binary members scanned unchanged: $($result.binary_members_scanned)"
        Write-Host "  exact identifier matches remaining: 0"
    }
}
finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
