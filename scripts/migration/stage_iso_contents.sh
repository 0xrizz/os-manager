#!/usr/bin/env bash
# scripts/migration/stage_iso_contents.sh - Extract & Stage Debian Live ISO to FAT32 DEBIAN_SET Partition
# Safely mounts the Debian Live ISO via loopback and copies the entire filesystem tree to the staging volume
set -euo pipefail

PWSH_BIN="${PWSH_BIN:-powershell.exe}"
if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
    if [[ -x "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" ]]; then
        PWSH_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    fi
fi

ISO_PATH="/mnt/d/download/debian-live-12.8.0-amd64-gnome.iso"
TARGET_DIR_OVERRIDE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --iso)
            ISO_PATH="${2:-}"
            shift 2
            ;;
        --target|--staging-dir)
            TARGET_DIR_OVERRIDE="${2:-}"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [ISO_PATH] [options]"
            echo ""
            echo "Options:"
            echo "  --iso <path>           Path to Debian Live ISO (default: /mnt/d/download/debian-live-12.8.0-amd64-gnome.iso)"
            echo "  --target <dir>         Override target staging directory (useful for verification)"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            if [[ -z "${1:-}" ]]; then
                shift
            elif [[ ! "$1" =~ ^- ]]; then
                ISO_PATH="$1"
                shift
            else
                echo "Unknown option: $1"
                exit 1
            fi
            ;;
    esac
done

echo "=================================================="
echo "Phase 2: Debian Live ISO Staging"
echo "=================================================="

# Verify ISO file existence
if [[ ! -f "$ISO_PATH" ]]; then
    echo "ERROR: Debian Live ISO file not found at: $ISO_PATH"
    echo "Please ensure the ISO has been acquired (run scripts/migration/verify_iso_squashfs.sh)."
    exit 1
fi

ISO_SIZE_BYTES=$(stat -c%s "$ISO_PATH" 2>/dev/null || stat -f%z "$ISO_PATH" 2>/dev/null || echo 0)
ISO_SIZE_GB=$(awk -v b="$ISO_SIZE_BYTES" 'BEGIN { printf "%.2f", b/1073741824 }')
echo "Source ISO: $ISO_PATH (${ISO_SIZE_GB} GB)"

# Resolve Staging Mount Directory
STAGING_MOUNT=""
STAGING_LETTER=""

if [[ -n "$TARGET_DIR_OVERRIDE" ]]; then
    STAGING_MOUNT="$TARGET_DIR_OVERRIDE"
    echo "Target directory overridden to: $STAGING_MOUNT"
else
    if ! command -v "$PWSH_BIN" >/dev/null 2>&1; then
        echo "ERROR: powershell.exe not found in PATH. Cannot resolve DEBIAN_SET drive letter."
        exit 1
    fi

    echo "Querying Windows for DEBIAN_SET staging volume..."
    STAGING_LETTER=$("$PWSH_BIN" -NoProfile -NonInteractive -Command "
        \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 25GB) }
        if (\$vol -and \$vol.DriveLetter) { Write-Output \$vol.DriveLetter }
    " < /dev/null 2>/dev/null | tr -d '\r\n')

    if [[ -z "$STAGING_LETTER" ]]; then
        echo "ERROR: Staging volume 'DEBIAN_SET' could not be resolved from Windows."
        echo "Please ensure the FAT32 staging partition (7GB - 25GB, labeled DEBIAN_SET) has been created and assigned a drive letter."
        echo "Refer to: docs/migration/PHASE_1_DISKGENIUS_GUIDE.md"
        exit 1
    fi

    STAGING_MOUNT="/mnt/${STAGING_LETTER,,}"
    echo "Staging drive resolved: ${STAGING_LETTER}: -> ${STAGING_MOUNT}"
fi

# Ensure target mount point is accessible
if [[ ! -d "$STAGING_MOUNT" ]]; then
    if [[ -n "$STAGING_LETTER" ]]; then
        echo "Mount point $STAGING_MOUNT not yet accessible in WSL. Attempting drvfs mount..."
        sudo mkdir -p "$STAGING_MOUNT"
        sudo mount -t drvfs "${STAGING_LETTER}:" "$STAGING_MOUNT" || true
    else
        mkdir -p "$STAGING_MOUNT"
    fi
fi

if [[ ! -d "$STAGING_MOUNT" || ! -w "$STAGING_MOUNT" ]]; then
    echo "ERROR: Cannot write to target mount directory: $STAGING_MOUNT"
    exit 1
fi

# Set up temporary loop mount directory in /var/tmp with safe trap cleanup
STAGE_TMP="$(mktemp -d /var/tmp/debian_iso_stage.XXXXXX)"

# shellcheck disable=SC2317
cleanup() {
    local exit_code=$?
    if mountpoint -q "$STAGE_TMP" 2>/dev/null; then
        echo "Unmounting temporary ISO loopback mount ($STAGE_TMP)..."
        sudo umount "$STAGE_TMP" 2>/dev/null || true
    fi
    if [[ -d "$STAGE_TMP" ]]; then
        rm -rf "$STAGE_TMP" 2>/dev/null || true
    fi
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

echo "Mounting ISO image loopback (read-only)..."
sudo mount -o loop,ro "$ISO_PATH" "$STAGE_TMP"

echo "Copying ISO filesystem tree to staging volume ($STAGING_MOUNT)..."
echo "(This may take 1-3 minutes depending on NVMe / FAT32 I/O speed)"

# Copy all contents including hidden metadata (.disk, etc.)
# Note: FAT32 does not support symlinks or Unix file permissions/timestamps
if command -v rsync >/dev/null 2>&1; then
    rsync -r --no-links --no-perms --no-owner --no-group --no-times --omit-dir-times "$STAGE_TMP/" "$STAGING_MOUNT/" 2>/dev/null || true
else
    cp -r "$STAGE_TMP"/. "$STAGING_MOUNT/" 2>/dev/null || true
fi

echo "Flushing disk write buffers (sync)..."
sync

echo "Verifying staged payload components on ${STAGING_MOUNT}:"
CHECKS_PASSED=true

# Verify EFI bootloader
if find "${STAGING_MOUNT}" -maxdepth 3 -iname "bootx64.efi" 2>/dev/null | grep -q .; then
    LOADER_PATH=$(find "${STAGING_MOUNT}" -maxdepth 3 -iname "bootx64.efi" 2>/dev/null | head -n 1)
    echo "  [OK] UEFI Bootloader: ${LOADER_PATH#"${STAGING_MOUNT}"/}"
else
    echo "  [ERROR] Missing EFI bootloader (bootx64.efi)!"
    CHECKS_PASSED=false
fi

# Verify Live filesystem squashfs
if [[ -f "${STAGING_MOUNT}/live/filesystem.squashfs" ]]; then
    SQUASH_SIZE=$(stat -c%s "${STAGING_MOUNT}/live/filesystem.squashfs" 2>/dev/null || stat -f%z "${STAGING_MOUNT}/live/filesystem.squashfs" 2>/dev/null || echo 0)
    SQUASH_GB=$(awk -v b="$SQUASH_SIZE" 'BEGIN { printf "%.2f", b/1073741824 }')
    echo "  [OK] SquashFS Root: live/filesystem.squashfs (${SQUASH_GB} GB)"
else
    echo "  [ERROR] Missing live/filesystem.squashfs!"
    CHECKS_PASSED=false
fi

# Verify Kernel and Initrd
if compgen -G "${STAGING_MOUNT}/live/vmlinuz*" > /dev/null && compgen -G "${STAGING_MOUNT}/live/initrd*" > /dev/null; then
    echo "  [OK] Kernel & Initrd: live/vmlinuz* and live/initrd*"
else
    echo "  [WARNING] Kernel or Initrd pattern not detected under live/"
fi

if [[ "$CHECKS_PASSED" != "true" ]]; then
    echo "ERROR: Staging validation failed. Some critical payload files were not copied."
    exit 1
fi

echo "=================================================="
echo "SUCCESS: Debian Live ISO payload staged successfully!"
echo "Target volume is ready for Phase 2 UEFI Boot Entry Registration."
echo "Next Step: Follow docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md"
echo "=================================================="
exit 0
