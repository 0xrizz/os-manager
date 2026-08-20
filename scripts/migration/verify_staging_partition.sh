#!/usr/bin/env bash
# scripts/migration/verify_staging_partition.sh - Validates Disk 0 Layout & DEBIAN_SET Staging Partition
# Queries Windows partition geometry and confirms FAT32 DEBIAN_SET staging volume state
set -euo pipefail

PWSH_BIN="${PWSH_BIN:-powershell.exe}"
if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    echo "ERROR: powershell.exe not found in PATH or standard Windows directory."
    exit 1
fi

echo "=================================================="
echo "Querying Disk 0 Partition Layout from Windows..."
echo "=================================================="

"$PWSH_BIN" -NoProfile -NonInteractive -Command "
    Get-Partition -DiskNumber 0 | Select-Object PartitionNumber, DriveLetter, Offset, Size, Type | Format-Table -AutoSize
" < /dev/null

echo "=================================================="
echo "Inspecting DEBIAN_SET Staging Volume Status..."
echo "=================================================="

"$PWSH_BIN" -NoProfile -NonInteractive -Command "
    \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 25GB) }
    if (\$vol) {
        \$drive = if (\$vol.DriveLetter) { \$vol.DriveLetter + ':' } else { '(No Drive Letter Assigned)' }
        \$sizeGb = [math]::Round(\$vol.Size / 1GB, 2)
        Write-Host ('SUCCESS: DEBIAN_SET detected at Drive ' + \$drive + ' (' + \$vol.FileSystem + ', ' + \$sizeGb + ' GB, Label: ' + \$vol.FileSystemLabel + ')')
    } else {
        Write-Host 'WARNING: DEBIAN_SET volume not found. Please create a FAT32 partition (flexible range: 7GB - 25GB, recommended 8GB - 15GB) labeled DEBIAN_SET via DiskGenius.'
    }
" < /dev/null

echo "=================================================="
