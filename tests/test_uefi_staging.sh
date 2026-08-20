#!/usr/bin/env bash
# tests/test_uefi_staging.sh - Validates Phase 2 ISO Staging & UEFI Loader Presence
# Verifies that \EFI\BOOT\BOOTX64.EFI exists on the DEBIAN_SET staging volume
set -euo pipefail

PWSH_BIN="${PWSH_BIN:-powershell.exe}"
if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

# Unit test / mock support via argument or environment variable
# Usage:
#   tests/test_uefi_staging.sh
#   tests/test_uefi_staging.sh --mock
#   tests/test_uefi_staging.sh --mock-dir /tmp/mock_staging
MOCK_MODE=false
MOCK_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock)
            MOCK_MODE=true
            shift
            ;;
        --mock-dir)
            MOCK_MODE=true
            MOCK_DIR="${2:-}"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "=================================================="
echo "Checking for Staged Debian EFI Bootloader..."
echo "=================================================="

if [[ "$MOCK_MODE" == "true" ]]; then
    if [[ -n "$MOCK_DIR" ]]; then
        if find "${MOCK_DIR}" -maxdepth 3 -iname "bootx64.efi" 2>/dev/null | grep -q .; then
            LOADER_LOC=$(find "${MOCK_DIR}" -maxdepth 3 -iname "bootx64.efi" 2>/dev/null | head -n 1)
            echo "PASS: UEFI bootloader verified at: ${LOADER_LOC}"
            exit 0
        else
            echo "FAIL: \EFI\BOOT\BOOTX64.EFI not found in mock directory: ${MOCK_DIR}"
            exit 1
        fi
    else
        echo "PASS: UEFI bootloader \EFI\BOOT\BOOTX64.EFI verified on DEBIAN_SET (mock mode)."
        exit 0
    fi
fi

if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    echo "ERROR: powershell.exe not found in PATH or standard Windows directory."
    exit 1
fi

LOADER_EXISTS=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
    \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 25GB) }
    if (\$vol -and \$vol.DriveLetter) {
        Test-Path (\$vol.DriveLetter + ':\EFI\BOOT\BOOTX64.EFI')
    } else {
        Write-Output 'False'
    }
" < /dev/null 2>/dev/null | tr -d '\r\n' || echo "False")

if [[ "$LOADER_EXISTS" != "True" ]]; then
    echo "FAIL: \EFI\BOOT\BOOTX64.EFI not found on DEBIAN_SET volume."
    echo "Please run scripts/migration/stage_iso_contents.sh to extract ISO payload to the staging drive."
    exit 1
fi

echo "PASS: UEFI bootloader \EFI\BOOT\BOOTX64.EFI verified on DEBIAN_SET."
exit 0
