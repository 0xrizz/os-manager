#!/usr/bin/env bash
# scripts/migration/export_disk_geometry_backup.sh - Windows Disk & BCD Redundancy Backup
# Exports GPT disk layout, partition geometry, and BCD configuration store to Drive D:
set -euo pipefail

BACKUP_DRIVE="${BACKUP_DRIVE:-D:}"
PWSH_BIN="${PWSH_BIN:-powershell.exe}"

if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

echo "Exporting Windows disk, partition, and BCD configuration to ${BACKUP_DRIVE}..."
"$PWSH_BIN" -NoProfile -NonInteractive -Command "
    Get-Disk | ConvertTo-Json -Depth 5 | Out-File -FilePath ${BACKUP_DRIVE}\disk_layout.json -Encoding utf8;
    Get-Partition | ConvertTo-Json -Depth 5 | Out-File -FilePath ${BACKUP_DRIVE}\partition_layout.json -Encoding utf8;
    bcdedit.exe /export ${BACKUP_DRIVE}\bcd_backup.bcd;
    Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem, SizeRemaining, Size | Format-Table -AutoSize
" < /dev/null

echo "SUCCESS: Redundancy backup exported to ${BACKUP_DRIVE}."
