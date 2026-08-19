<#
.SYNOPSIS
    Automated WSL2 Distro Provisioning & Disaster Recovery Engine for os-manager.
.DESCRIPTION
    Discovers point-in-time snapshot archives, verifies cryptographic SHA-256 checksums,
    allocates target virtual disk storage, imports the WSL2 instance, configures the
    default login user in /etc/wsl.conf, and triggers the Linux post-bootstrap agent.
.PARAMETER SnapshotPath
    Path to the .tar.gz or .tar snapshot archive. Defaults to the latest file in D:\wsl_backup\.
.PARAMETER InstanceName
    Name of the new WSL2 instance. Defaults to Debian-Restored-<Timestamp>.
.PARAMETER InstallLocation
    Directory to store the virtual disk (.vhdx). Defaults to D:\WSL\<InstanceName>.
.PARAMETER DefaultUser
    Linux username for default shell login. Defaults to 'rizz'.
.PARAMETER SetAsDefault
    Sets the imported instance as the default WSL distribution.
.PARAMETER SkipChecksum
    Bypasses SHA-256 integrity verification.
.PARAMETER DryRun
    Simulates discovery, parameter calculation, and checksum validation without importing.
.PARAMETER Force
    Overwrites an existing directory or deregisters a conflicting instance name.
.PARAMETER SkipPostBootstrap
    Bypasses execution of scripts/post_bootstrap.sh after instance import.
.EXAMPLE
    .\scripts\bootstrap_wsl.ps1 -DryRun
.EXAMPLE
    .\scripts\bootstrap_wsl.ps1 -InstanceName "Debian-Production" -SetAsDefault
#>
[CmdletBinding()]
param(
    [string]$SnapshotPath,
    [string]$InstanceName,
    [string]$InstallLocation,
    [string]$DefaultUser = "rizz",
    [switch]$SetAsDefault,
    [switch]$SkipChecksum,
    [switch]$DryRun,
    [switch]$Force,
    [switch]$SkipPostBootstrap
)

$ErrorActionPreference = "Stop"

$BackupDirectory = "D:\wsl_backup"
$DefaultWslRoot = "D:\WSL"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " OS-Manager Automated WSL2 Disaster Recovery Provisioner" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Resolve Snapshot Archive
if (-not $SnapshotPath) {
    if (-not (Test-Path $BackupDirectory)) {
        throw "Backup directory '$BackupDirectory' does not exist."
    }
    $LatestSnapshot = Get-ChildItem -Path "$BackupDirectory\*.tar*", "$BackupDirectory\*.tar.gz" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $LatestSnapshot) {
        throw "No snapshot archives (.tar / .tar.gz) found in '$BackupDirectory'."
    }
    $SnapshotPath = $LatestSnapshot.FullName
}

if (-not (Test-Path $SnapshotPath)) {
    throw "Specified snapshot path does not exist: $SnapshotPath"
}

Write-Host "==> Selected snapshot archive: $SnapshotPath" -ForegroundColor Green

# 2. Checksum Verification
if (-not $SkipChecksum) {
    $ChecksumFile = "$SnapshotPath.sha256"
    if (Test-Path $ChecksumFile) {
        Write-Host "==> Verifying SHA-256 checksum against sidecar..." -ForegroundColor Gray
        $ExpectedHash = (Get-Content $ChecksumFile | Select-Object -First 1).Split(' ')[0].Trim()
        $ActualHash = (Get-FileHash -Path $SnapshotPath -Algorithm SHA256).Hash.ToLower()

        if ($ExpectedHash.ToLower() -ne $ActualHash) {
            throw "Checksum mismatch! Expected: $ExpectedHash, Actual: $ActualHash"
        }
        Write-Host "==> Cryptographic checksum verified successfully: $ActualHash" -ForegroundColor Green
    } else {
        Write-Warning "Checksum file '$ChecksumFile' missing. Skipping verification."
    }
} else {
    Write-Warning "SHA-256 checksum verification skipped (-SkipChecksum)."
}

# 3. Establish Instance Parameters
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $InstanceName) {
    $InstanceName = "Debian-Restored-$Timestamp"
}
if (-not $InstallLocation) {
    $InstallLocation = Join-Path $DefaultWslRoot $InstanceName
}

Write-Host "==> Target Instance Name   : $InstanceName" -ForegroundColor Gray
Write-Host "==> Target Install Location: $InstallLocation" -ForegroundColor Gray
Write-Host "==> Default User           : $DefaultUser" -ForegroundColor Gray

# 4. Storage & Collision Validation
if (Test-Path $InstallLocation) {
    if ($Force) {
        Write-Warning "Directory '$InstallLocation' exists. Overwriting (-Force)..."
        if (-not $DryRun) {
            Remove-Item -Path $InstallLocation -Recurse -Force
        }
    } else {
        throw "Install location '$InstallLocation' already exists. Use -Force to overwrite."
    }
}

$DriveLetter = (Get-Item (Split-Path $InstallLocation -Parent)).PSDrive.Name
if (-not $DriveLetter) {
    $DriveLetter = "D"
}

try {
    $Volume = Get-Volume -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
    if ($Volume) {
        $FreeSpaceGB = [math]::Round($Volume.SizeRemaining / 1GB, 2)
        Write-Host "==> Available space on drive ${DriveLetter}: : ${FreeSpaceGB} GB" -ForegroundColor Gray
        if ($FreeSpaceGB -lt 25) {
            throw "Insufficient disk space on drive ${DriveLetter}: (${FreeSpaceGB}GB free, 25GB required)."
        }
    }
} catch {
    Write-Warning "Could not verify drive volume free space: $_"
}

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY-RUN] Simulation successful. Target execution commands:" -ForegroundColor Yellow
    Write-Host "  1. New-Item -ItemType Directory -Path '$InstallLocation' -Force" -ForegroundColor Yellow
    Write-Host "  2. wsl.exe --import '$InstanceName' '$InstallLocation' '$SnapshotPath' --version 2" -ForegroundColor Yellow
    Write-Host "  3. wsl.exe -d '$InstanceName' -u root -- bash -c '[user]\ndefault=$DefaultUser > /etc/wsl.conf'" -ForegroundColor Yellow
    Write-Host "  4. wsl.exe -d '$InstanceName' -u '$DefaultUser' -- bash scripts/post_bootstrap.sh" -ForegroundColor Yellow
    exit 0
}

# 5. Import WSL2 Instance
New-Item -ItemType Directory -Path $InstallLocation -Force | Out-Null
Write-Host "==> Importing WSL2 instance '$InstanceName' from snapshot..." -ForegroundColor Green
wsl.exe --import $InstanceName $InstallLocation $SnapshotPath --version 2
if ($LASTEXITCODE -ne 0) {
    throw "wsl.exe --import failed with exit code $LASTEXITCODE."
}

# 6. Configure Default User
Write-Host "==> Configuring default user '$DefaultUser' and systemd in /etc/wsl.conf..." -ForegroundColor Green
$WslConfContent = "[user]`ndefault=$DefaultUser`n`n[boot]`nsystemd=true`n"
$WslConfCommand = "cat <<'EOF' > /etc/wsl.conf`n$WslConfContent`nEOF"
wsl.exe -d $InstanceName -u root -- bash -c "$WslConfCommand"

# 7. Execute Linux Post-Bootstrap Verification Agent
if (-not $SkipPostBootstrap) {
    Write-Host "==> Executing Linux post-bootstrap verification agent..." -ForegroundColor Green
    $PostBootstrapCommand = "TARGET_SCRIPT=`$(find /home/$DefaultUser/dev/os-manager/scripts/post_bootstrap.sh -type f 2>/dev/null | head -n 1); if [ -n `"`$TARGET_SCRIPT`" ]; then bash `"`$TARGET_SCRIPT`"; else echo 'Post-bootstrap script not found in standard workspace.'; fi"
    wsl.exe -d $InstanceName -u $DefaultUser -- bash -c "$PostBootstrapCommand"
}

if ($SetAsDefault) {
    Write-Host "==> Setting '$InstanceName' as default WSL instance..." -ForegroundColor Green
    wsl.exe --set-default $InstanceName
}

Write-Host ""
Write-Host "==> Provisioning complete. Launch instance using:" -ForegroundColor Cyan
Write-Host "    wsl -d $InstanceName" -ForegroundColor White
