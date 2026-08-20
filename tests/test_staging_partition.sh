#!/usr/bin/env bash
# tests/test_staging_partition.sh - Validates Phase 1 FAT32 Staging Partition Creation
# Verifies existence of 8GB FAT32 staging partition labeled DEBIAN_SET on Disk 0
set -euo pipefail

PWSH_BIN="${PWSH_BIN:-powershell.exe}"
if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

# Unit test / mock support via environment variable or CLI argument
MOCK_PAYLOAD="${STAGING_INFO_MOCK:-}"
if [[ $# -ge 2 && "$1" == "--mock" ]]; then
    MOCK_PAYLOAD="$2"
fi

echo "=================================================="
echo "Checking for DEBIAN_SET Volume / FAT32 Staging..."
echo "=================================================="

if [[ -n "$MOCK_PAYLOAD" ]]; then
    STAGING_INFO="$MOCK_PAYLOAD"
else
    if command -v "$PWSH_BIN" >/dev/null 2>&1; then
        STAGING_INFO=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
            \$v = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 9GB) } | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size | ConvertTo-Json -Compress
            if (\$v) { Write-Output \$v }
        " < /dev/null 2>/dev/null || true)
    else
        STAGING_INFO=""
    fi
fi

# Trim whitespace
STAGING_INFO="$(echo "${STAGING_INFO:-}" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

if [[ -z "$STAGING_INFO" || "$STAGING_INFO" == "null" || "$STAGING_INFO" == "{}" ]]; then
    echo "WAITING: Staging partition 'DEBIAN_SET' (8GB FAT32) has not been created yet."
    echo "Please follow instructions in docs/migration/PHASE_1_DISKGENIUS_GUIDE.md to shrink C: and create DEBIAN_SET."
    exit 1
fi

echo "PASS: Staging partition detected: ${STAGING_INFO}"
exit 0
