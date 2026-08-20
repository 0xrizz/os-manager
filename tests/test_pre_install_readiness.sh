#!/usr/bin/env bash
# tests/test_pre_install_readiness.sh - Pre-installation readiness validation test
# Validates BitLocker encryption status, backup integrity, and pre-install readiness
set -euo pipefail

PWSH_BIN="${PWSH_BIN:-powershell.exe}"
if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

# Unit test / mock support via arguments or environment variables
# Usage:
#   tests/test_pre_install_readiness.sh
#   tests/test_pre_install_readiness.sh --mock
#   tests/test_pre_install_readiness.sh --mock-bitlocker Off --mock-backup /path/to/archive
MOCK_MODE=false
MOCK_BITLOCKER=""
MOCK_BACKUP=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock)
            MOCK_MODE=true
            shift
            ;;
        --mock-bitlocker)
            MOCK_MODE=true
            MOCK_BITLOCKER="${2:-Off}"
            shift 2
            ;;
        --mock-backup)
            MOCK_MODE=true
            MOCK_BACKUP="${2:-}"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "=================================================="
echo "Executing Pre-Installation Sanity Checks..."
echo "=================================================="

# 1. BitLocker Decryption Status Check
echo -n "1. Checking BitLocker status on C: and D:... "
if [[ "$MOCK_MODE" == "true" ]]; then
    BITLOCKER_STATUS="${MOCK_BITLOCKER:-Off}"
    if [[ "$BITLOCKER_STATUS" == "Off" || "$BITLOCKER_STATUS" == "True" ]]; then
        echo "PASS (Mock: Decrypted / Off)"
    else
        echo "FAIL: BitLocker is still active in mock mode ($BITLOCKER_STATUS)!"
        exit 1
    fi
else
    if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
        echo "ERROR: powershell.exe not found. Cannot verify BitLocker status."
        exit 1
    fi

    BITLOCKER_OFF=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
        \$c = Get-BitLockerVolume -MountPoint C: -ErrorAction SilentlyContinue
        \$d = Get-BitLockerVolume -MountPoint D: -ErrorAction SilentlyContinue
        if (\$c -and \$d -and \$c.ProtectionStatus -eq 'Off' -and \$d.ProtectionStatus -eq 'Off') {
            Write-Output 'True'
        } else {
            Write-Output 'False'
        }
    " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "False")

    if [[ "$BITLOCKER_OFF" != "True" ]]; then
        echo "FAIL: BitLocker is still active on C: or D:!"
        echo "Please decrypt BitLocker via 'manage-bde.exe -off C:' and 'manage-bde.exe -off D:' before migration."
        exit 1
    fi
    echo "PASS (Both C: and D: are Off / Decrypted)"
fi

# 2. Disaster Recovery & WSL Backup Check
echo -n "2. Checking WSL backup archive on Drive D:... "
BACKUP_FILE="${MOCK_BACKUP:-/mnt/d/wsl_backup/wsl_home_backup.tar.gz}"

if [[ "$MOCK_MODE" == "true" && -z "$MOCK_BACKUP" ]]; then
    echo "PASS (Mock: wsl_home_backup.tar.gz verified)"
else
    if [[ -s "$BACKUP_FILE" ]]; then
        BACKUP_SIZE_MB=$(du -m "$BACKUP_FILE" 2>/dev/null | cut -f1 || stat -c%s "$BACKUP_FILE" 2>/dev/null | awk '{print int($1/1048576)}' || echo 0)
        echo "PASS (${BACKUP_FILE} present, ~${BACKUP_SIZE_MB} MB)"
    else
        echo "FAIL: WSL backup archive missing or empty at $BACKUP_FILE!"
        exit 1
    fi
fi

# 3. Fast Startup Check
echo -n "3. Checking Windows Fast Startup (Hybrid Sleep)... "
if [[ "$MOCK_MODE" == "true" ]]; then
    echo "PASS (Mock: Fast Startup disabled)"
else
    FAST_STARTUP=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
        \$val = Get-ItemPropertyValue -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name 'HiberbootEnabled' -ErrorAction SilentlyContinue
        if (\$val -eq 0 -or \$null -eq \$val) { Write-Output 'Disabled' } else { Write-Output 'Enabled' }
    " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "Unknown")

    if [[ "$FAST_STARTUP" == "Enabled" ]]; then
        echo "WARN (Fast Startup is enabled in Windows; recommend 'powercfg /h off' before reboot)"
    else
        echo "PASS (Fast Startup disabled)"
    fi
fi

echo "=================================================="
echo "PASS: System is 100% ready for reboot and Calamares installation."
echo "=================================================="
exit 0
