#!/usr/bin/env bash
# scripts/migration/verify_reclaimed_geometry.sh - Audits SSD layout and unallocated capacity
set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

DISK="/dev/nvme0n1"
DRY_RUN=false

show_help() {
    cat << 'HELP_EOF'
Usage: verify_reclaimed_geometry.sh [options]

Audits SSD partition layout, unallocated space, and critical mount points
(/, /mnt/data, /boot/efi) on the target NVMe drive.

Options:
  -d, --dry-run     Simulate geometry audit and show anticipated partition layout
  --disk <path>     Target block device (default: /dev/nvme0n1)
  -h, --help        Show this help message and exit

Examples:
  ./scripts/migration/verify_reclaimed_geometry.sh --dry-run
  ./scripts/migration/verify_reclaimed_geometry.sh --disk /dev/nvme0n1
HELP_EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --disk)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --disk requires a device path argument." >&2
                exit 1
            fi
            DISK="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$1'. Use --help for usage details." >&2
            exit 1
            ;;
    esac
done

echo "=================================================="
echo "    NVMe SSD PARTITION & GEOMETRY AUDIT           "
echo "=================================================="
echo "Disk Device: ${DISK}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Geometry summary:"
    echo "  - EFI System Partition   : ${DISK}p1 (100 MB, FAT32 -> /boot/efi)"
    echo "  - Debian Root Partition  : ${DISK}p6 (71 GB ext4, expandable to ~235 GB -> /)"
    echo "  - Preserved DATA_STORE   : ${DISK}p4 (244 GB NTFS, intact -> /mnt/data)"
    echo "  - Reclaimed Space        : ~160 GB unallocated"
    echo "=================================================="
    echo "STATUS: Geometry audit complete (DRY RUN)."
    echo "=================================================="
    exit 0
fi

if [[ -b "${DISK}" ]]; then
    echo "Partition Layout (lsblk):"
    lsblk -o NAME,SIZE,START,FSTYPE,LABEL,MOUNTPOINTS "${DISK}" || true
    
    echo ""
    echo "Detailed Partition & Free Space Layout (parted):"
    if command -v parted >/dev/null 2>&1; then
        if [[ $EUID -eq 0 ]]; then
            parted -s "${DISK}" unit GiB print free || true
        elif sudo -n true 2>/dev/null; then
            sudo parted -s "${DISK}" unit GiB print free || true
        else
            parted -s "${DISK}" unit GiB print free 2>/dev/null || true
        fi
    fi

    echo ""
    echo "Active Mount Point Verification:"
    echo "  - Root (/):"
    findmnt / || echo "    Notice: Root mountpoint not detected"
    echo "  - Data Store (/mnt/data):"
    findmnt /mnt/data || echo "    Notice: /mnt/data mountpoint not mounted"
    echo "  - EFI ESP (/boot/efi):"
    findmnt /boot/efi || echo "    Notice: /boot/efi mountpoint not mounted"
else
    echo "Notice: Disk ${DISK} not detected directly as a block device in current environment."
    echo ""
    echo "Current Active Mount Points:"
    findmnt / || true
    findmnt /mnt/data || true
    findmnt /boot/efi || true
fi

echo "=================================================="
echo "STATUS: Geometry audit complete."
echo "=================================================="
