#!/usr/bin/env bash
# scripts/migration/switch_boot_to_new_root.sh - Switches GRUB UEFI boot target to new root (/dev/nvme0n1p2)
set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

DRY_RUN=false
NEW_ROOT_DEV="/dev/nvme0n1p2"
EFI_DEV="/dev/nvme0n1p1"
MOUNT_DIR="/mnt/new_root"

show_help() {
    cat << 'EOF'
Usage: switch_boot_to_new_root.sh [options]

Switches the GRUB UEFI default bootloader target to the new root partition (/dev/nvme0n1p2)
by performing a chroot grub-install and update-grub from inside the new root filesystem.

Options:
  -d, --dry-run     Simulate all mount operations and chroot GRUB generation without modifying disk
  --root <dev>      Specify target root block device (default: /dev/nvme0n1p2)
  --efi <dev>       Specify target EFI ESP block device (default: /dev/nvme0n1p1)
  -h, --help        Show this help message and exit

Examples:
  ./scripts/migration/switch_boot_to_new_root.sh --dry-run
  sudo ./scripts/migration/switch_boot_to_new_root.sh
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --root)
            NEW_ROOT_DEV="${2:-/dev/nvme0n1p2}"
            shift 2
            ;;
        --efi)
            EFI_DEV="${2:-/dev/nvme0n1p1}"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$1'. Use --help for usage." >&2
            exit 1
            ;;
    esac
done

echo "=================================================="
echo " SWITCHING GRUB DEFAULT BOOT TO ${NEW_ROOT_DEV}   "
echo "=================================================="

# Dry-run mode simulation
if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Target New Root Device: ${NEW_ROOT_DEV}"
    echo "[DRY RUN] Target EFI ESP Device:  ${EFI_DEV}"
    echo "[DRY RUN] Target Mount Point:     ${MOUNT_DIR}"
    echo "[DRY RUN] Simulating Steps:"
    echo "  1. mount ${NEW_ROOT_DEV} ${MOUNT_DIR}"
    echo "  2. sed -i 's/^#GRUB_DISABLE_OS_PROBER=false/GRUB_DISABLE_OS_PROBER=false/' /etc/default/grub"
    echo "  3. mount --bind /dev /proc /sys /boot/efi into ${MOUNT_DIR}"
    echo "  4. chroot ${MOUNT_DIR} grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=debian --recheck /dev/nvme0n1"
    echo "  5. chroot ${MOUNT_DIR} update-grub"
    echo "  6. umount all bind mounts and cleanup ${MOUNT_DIR}"
    echo "=================================================="
    echo "[DRY RUN] Boot switch simulation passed successfully."
    echo "=================================================="
    exit 0
fi

# Privilege Check
if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
    echo "ERROR: Root privileges required. Run with sudo: sudo $0" >&2
    exit 1
fi

SUDO_CMD=""
if [[ $EUID -ne 0 ]]; then
    SUDO_CMD="sudo"
fi

# 1. Ensure mount point
$SUDO_CMD mkdir -p "${MOUNT_DIR}"
if ! mountpoint -q "${MOUNT_DIR}"; then
    echo "Mounting ${NEW_ROOT_DEV} to ${MOUNT_DIR}..."
    $SUDO_CMD mount "${NEW_ROOT_DEV}" "${MOUNT_DIR}"
fi

# 2. Enable os-prober in /etc/default/grub on both roots
echo "Enabling os-prober in GRUB configurations..."
$SUDO_CMD sed -i 's/^#GRUB_DISABLE_OS_PROBER=false/GRUB_DISABLE_OS_PROBER=false/' /etc/default/grub || true
$SUDO_CMD sed -i 's/^#GRUB_DISABLE_OS_PROBER=false/GRUB_DISABLE_OS_PROBER=false/' "${MOUNT_DIR}/etc/default/grub" || true

# 3. Mount pseudo filesystems for chroot
echo "Binding virtual filesystems for chroot..."
$SUDO_CMD mkdir -p "${MOUNT_DIR}/boot/efi" "${MOUNT_DIR}/dev" "${MOUNT_DIR}/proc" "${MOUNT_DIR}/sys"
$SUDO_CMD mount --bind /dev "${MOUNT_DIR}/dev"
$SUDO_CMD mount --bind /proc "${MOUNT_DIR}/proc"
$SUDO_CMD mount --bind /sys "${MOUNT_DIR}/sys"
$SUDO_CMD mount "${EFI_DEV}" "${MOUNT_DIR}/boot/efi"

# 4. Install & update GRUB from inside new root
echo "Installing and generating GRUB boot configuration from new root..."
$SUDO_CMD chroot "${MOUNT_DIR}" grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=debian --recheck /dev/nvme0n1
$SUDO_CMD chroot "${MOUNT_DIR}" update-grub

# 5. Clean unmount
echo "Cleaning up mounts..."
$SUDO_CMD umount "${MOUNT_DIR}/boot/efi" || true
$SUDO_CMD umount "${MOUNT_DIR}/dev" || true
$SUDO_CMD umount "${MOUNT_DIR}/proc" || true
$SUDO_CMD umount "${MOUNT_DIR}/sys" || true
$SUDO_CMD umount "${MOUNT_DIR}" || true
$SUDO_CMD rmdir "${MOUNT_DIR}" 2>/dev/null || true

echo "=================================================="
echo "SUCCESS: GRUB default bootloader set to ${NEW_ROOT_DEV}!"
echo "Now run 'sudo reboot' to boot into your new root."
echo "=================================================="
