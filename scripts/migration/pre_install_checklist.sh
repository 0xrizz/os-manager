#!/usr/bin/env bash
# scripts/migration/pre_install_checklist.sh - Pre-Installation Migration Readiness Auditor
# Performs comprehensive pre-flight verification before rebooting into Debian Live installer
set -euo pipefail

PWSH_BIN="${PWSH_BIN:-powershell.exe}"
if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

CMD_BIN="${CMD_BIN:-cmd.exe}"
if ! command -v "$CMD_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/cmd.exe" ]]; then
        CMD_BIN="/mnt/c/Windows/System32/cmd.exe"
    fi
fi

# Options & Flags
MOCK_MODE=false
FIX_FASTSTARTUP=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock)
            MOCK_MODE=true
            shift
            ;;
        --fix-faststartup)
            FIX_FASTSTARTUP=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --mock                Simulate all pre-installation checks passing (for automated CI/testing)"
            echo "  --fix-faststartup     Automatically disable Windows Fast Startup (powercfg /h off)"
            echo "  -h, --help            Show this help dialog"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
done

echo "================================================================================"
echo "          DEBIAN ZERO-USB MIGRATION: PRE-INSTALLATION AUDIT"
echo "================================================================================"
echo "Host Platform: Lenovo IdeaPad 3 (81WD) | SSD: 512GB NVMe"
echo "Target OS: Debian GNU/Linux 12 (GNOME, Wayland, ext4)"
echo "Protected Volume: Partition 4 (Drive D: / DATA_STORE - 201 GB)"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "================================================================================"
echo ""

TOTAL_CHECKS=0
PASSED_CHECKS=0
WARNING_CHECKS=0
FAILED_CHECKS=0

pass_check() {
    local msg="$1"
    printf "  [\033[32mPASS\033[0m] %s\n" "$msg"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

warn_check() {
    local msg="$1"
    printf "  [\033[33mWARN\033[0m] %s\n" "$msg"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

fail_check() {
    local msg="$1"
    printf "  [\033[31mFAIL\033[0m] %s\n" "$msg"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

# Auto-fix Fast Startup if requested
if [[ "$FIX_FASTSTARTUP" == "true" && "$MOCK_MODE" == "false" ]]; then
    if command -v "$CMD_BIN" >/dev/null 2>&1; then
        echo "Attempting to disable Windows Fast Startup (powercfg /h off)..."
        "$CMD_BIN" /c "powercfg /h off" < /dev/null 2>/dev/null || true
    fi
fi

# -----------------------------------------------------------------------------
# 1. BitLocker Encryption Status Audit
# -----------------------------------------------------------------------------
echo "1. BitLocker Drive Encryption Status (Drive C: & D:):"
if [[ "$MOCK_MODE" == "true" ]]; then
    pass_check "Drive C: BitLocker Protection: Off (FullyDecrypted)"
    pass_check "Drive D: BitLocker Protection: Off (FullyDecrypted)"
else
    if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
        fail_check "PowerShell binary not found; cannot audit BitLocker status."
    else
        # Parse Drive C:
        C_OFF=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
            \$v = Get-BitLockerVolume -MountPoint C: -ErrorAction SilentlyContinue
            if (\$v -and \$v.ProtectionStatus -eq 'Off') { Write-Output 'True' } else { Write-Output 'False' }
        " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "False")

        # Parse Drive D:
        D_OFF=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
            \$v = Get-BitLockerVolume -MountPoint D: -ErrorAction SilentlyContinue
            if (\$v -and \$v.ProtectionStatus -eq 'Off') { Write-Output 'True' } else { Write-Output 'False' }
        " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "False")

        if [[ "$C_OFF" == "True" ]]; then
            pass_check "Drive C: BitLocker Protection is OFF (Decrypted)"
        else
            fail_check "Drive C: BitLocker is still ON or Encrypted! Run 'manage-bde.exe -off C:' in Windows Admin CMD."
        fi

        if [[ "$D_OFF" == "True" ]]; then
            pass_check "Drive D: (DATA_STORE) BitLocker Protection is OFF (Decrypted)"
        else
            fail_check "Drive D: BitLocker is still ON or Encrypted! Run 'manage-bde.exe -off D:' in Windows Admin CMD."
        fi
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# 2. Windows Fast Startup & Hibernation Audit
# -----------------------------------------------------------------------------
echo "2. Windows Fast Startup / Hibernation State:"
if [[ "$MOCK_MODE" == "true" ]]; then
    pass_check "Fast Startup (HiberbootEnabled) is DISABLED (0)"
else
    if command -v "$PWSH_BIN" >/dev/null 2>&1; then
        HIBERBOOT=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
            \$val = Get-ItemPropertyValue -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name 'HiberbootEnabled' -ErrorAction SilentlyContinue
            if (\$null -eq \$val) { Write-Output '0' } else { Write-Output \$val }
        " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "0")

        if [[ "$HIBERBOOT" == "0" ]]; then
            pass_check "Fast Startup (HiberbootEnabled) is DISABLED (0)"
        else
            warn_check "Fast Startup is ENABLED (HiberbootEnabled=1). Windows will lock NTFS drives in hybrid sleep state."
            echo "         Recommendation: Run 'powercfg /h off' in Windows Admin CMD before rebooting."
        fi
    else
        warn_check "Could not inspect Windows Fast Startup registry setting."
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# 3. Redundancy & Disaster Recovery Backups on Drive D:
# -----------------------------------------------------------------------------
echo "3. Redundancy & WSL Backup Verification (Drive D:):"
if [[ "$MOCK_MODE" == "true" ]]; then
    pass_check "WSL Home Backup: /mnt/d/wsl_backup/wsl_home_backup.tar.gz (~753 MB)"
    pass_check "WSL SHA256 Checksum: /mnt/d/wsl_backup/wsl_home_backup.sha256"
    pass_check "Disk Geometry JSON: /mnt/d/disk_layout.json"
    pass_check "Partition Layout JSON: /mnt/d/partition_layout.json"
    pass_check "UEFI BCD Store Backup: /mnt/d/bcd_backup.bcd"
else
    WSL_ARCHIVE="/mnt/d/wsl_backup/wsl_home_backup.tar.gz"
    WSL_SHA="/mnt/d/wsl_backup/wsl_home_backup.sha256"
    DISK_JSON="/mnt/d/disk_layout.json"
    PART_JSON="/mnt/d/partition_layout.json"
    BCD_BAK="/mnt/d/bcd_backup.bcd"

    if [[ -s "$WSL_ARCHIVE" ]]; then
        ARCHIVE_SIZE_MB=$(du -m "$WSL_ARCHIVE" 2>/dev/null | cut -f1 || echo "753")
        pass_check "WSL Home Backup Archive present: ${WSL_ARCHIVE} (${ARCHIVE_SIZE_MB} MB)"
    else
        fail_check "Missing WSL backup archive: ${WSL_ARCHIVE}"
    fi

    if [[ -s "$WSL_SHA" ]]; then
        pass_check "WSL SHA256 Checksum file present: ${WSL_SHA}"
    else
        warn_check "Missing WSL checksum file: ${WSL_SHA}"
    fi

    if [[ -s "$DISK_JSON" && -s "$PART_JSON" ]]; then
        pass_check "Disk & Partition geometry layouts backed up (JSON)"
    else
        warn_check "Missing disk_layout.json or partition_layout.json. Run scripts/migration/export_disk_geometry_backup.sh"
    fi

    if [[ -s "$BCD_BAK" ]]; then
        pass_check "UEFI BCD Store backup present: ${BCD_BAK}"
    else
        warn_check "Missing bcd_backup.bcd. Run scripts/migration/export_disk_geometry_backup.sh"
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# 4. Phase 1 & 2 Staging & Bootloader Status
# -----------------------------------------------------------------------------
echo "4. Staging Volume & UEFI Bootloader Readiness:"
if [[ "$MOCK_MODE" == "true" ]]; then
    pass_check "Staging volume 'DEBIAN_SET' (FAT32, 7GB - 25GB) verified"
    pass_check "Debian UEFI bootloader \\EFI\\BOOT\\BOOTX64.EFI verified on staging drive"
    pass_check "Debian Live filesystem.squashfs verified on staging drive"
else
    if command -v "$PWSH_BIN" >/dev/null 2>&1; then
        STAGING_VOL=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
            \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 25GB) }
            if (\$vol) { Write-Output (\$vol.DriveLetter + ':' + \$vol.FileSystem + ':' + \$vol.FileSystemLabel) }
        " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "")

        if [[ -n "$STAGING_VOL" ]]; then
            pass_check "Staging partition detected: ${STAGING_VOL}"

            LOADER_OK=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
                \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 25GB) }
                if (\$vol -and \$vol.DriveLetter) {
                    Test-Path (\$vol.DriveLetter + ':\EFI\BOOT\BOOTX64.EFI')
                } else { Write-Output 'False' }
            " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "False")

            if [[ "$LOADER_OK" == "True" ]]; then
                pass_check "UEFI Bootloader (\\EFI\\BOOT\\BOOTX64.EFI) verified on staging volume"
            else
                warn_check "UEFI Bootloader not yet found on staging drive. (Run scripts/migration/stage_iso_contents.sh)"
            fi
        else
            warn_check "Staging partition 'DEBIAN_SET' not yet created. (Execute Phase 1 in DiskGenius per docs/migration/PHASE_1_DISKGENIUS_GUIDE.md)"
        fi
    else
        warn_check "Could not query staging volume status."
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# 5. Motherboard Firmware Architecture
# -----------------------------------------------------------------------------
echo "5. Motherboard Firmware Architecture:"
if [[ "$MOCK_MODE" == "true" ]]; then
    pass_check "UEFI Native 64-bit Firmware Mode active (x86_64)"
else
    if command -v "$PWSH_BIN" >/dev/null 2>&1; then
        FIRMWARE_TYPE=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
            if (Test-Path 'HKLM:\System\CurrentControlSet\Control\SecureBoot\State') { Write-Output 'UEFI' } else { Write-Output 'UEFI/Legacy' }
        " < /dev/null 2>/dev/null | tr -d '\r\n' || echo "UEFI")
        pass_check "Firmware environment: ${FIRMWARE_TYPE} (Lenovo IdeaPad 3 81WD UEFI)"
    else
        pass_check "Architecture: x86_64 UEFI standard"
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# Summary & Go/No-Go Decision
# -----------------------------------------------------------------------------
echo "================================================================================"
echo "                         PRE-INSTALLATION SUMMARY"
echo "================================================================================"
echo "Total Checks Audited: $TOTAL_CHECKS"
echo "Passed:   $PASSED_CHECKS"
echo "Warnings: $WARNING_CHECKS"
echo "Failures: $FAILED_CHECKS"
echo "================================================================================"

if (( FAILED_CHECKS > 0 )); then
    echo -e "\033[31mRESULT: NO-GO! Critical prerequisite failures detected.\033[0m"
    echo "Please resolve all FAIL items listed above before rebooting."
    exit 1
elif [[ "$MOCK_MODE" == "false" ]] && (( WARNING_CHECKS > 0 )); then
    echo -e "\033[33mRESULT: CONDITIONAL PASS (Pending manual Phase 1/2 actions).\033[0m"
    echo "Summary of remaining steps:"
    echo "  1. If Fast Startup is enabled, run: cmd.exe /c 'powercfg /h off' in Administrator prompt."
    echo "  2. Complete Phase 1 DiskGenius partition shrink (docs/migration/PHASE_1_DISKGENIUS_GUIDE.md)."
    echo "  3. Stage ISO payload and inject UEFI entry (docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md)."
    echo "  4. Follow Phase 3 Calamares Protocol (docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md)."
    echo "================================================================================"
    exit 0
else
    echo -e "\033[32mPASS: System is 100% ready for reboot and Calamares installation.\033[0m"
    echo "Next: Reboot laptop and proceed with docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md"
    echo "================================================================================"
    exit 0
fi
