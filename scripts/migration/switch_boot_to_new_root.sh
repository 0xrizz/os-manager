#!/usr/bin/env bash
# scripts/migration/switch_boot_to_new_root.sh - Switches GRUB UEFI boot target to new root (/dev/nvme0n1p2)
set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

NEW_ROOT_DEV="/dev/nvme0n1p2"
EFI_DEV="/dev/nvme0n1p1"
MOUNT_DIR="/mnt/new_root"

if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
    echo "ERROR: Root privileges required. Run with sudo: sudo $0" >&2
    exit 1
fi

SUDO_CMD=""
if [[ $EUID -ne 0 ]]; then
    SUDO_CMD="sudo"
fi

echo "=================================================="
echo " SWITCHING GRUB DEFAULT BOOT TO /dev/nvme0n1p2   "
echo "=================================================="

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
echo "SUCCESS: GRUB default bootloader set to /dev/nvme0n1p2!"
echo "Now run 'sudo reboot' to boot into your new root."
echo "=================================================="
