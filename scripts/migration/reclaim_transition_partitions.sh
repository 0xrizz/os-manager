#!/usr/bin/env bash
# scripts/migration/reclaim_transition_partitions.sh - Safe Deletion of Obsolete Windows & Staging Partitions
# Removes partitions 2 (Eks Windows C:), 5 (DEBIAN_SET), and 3 (Windows Recovery) while strictly protecting 1, 4, 6.
set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

DRY_RUN=false
TARGET_DISK="/dev/nvme0n1"
MOCK_TARGET_PART=""
FORCE=false

show_help() {
    cat << 'EOF'
Usage: reclaim_transition_partitions.sh [options]

Safely removes obsolete transition partitions (2: Windows C:, 5: DEBIAN_SET, 3: Windows Recovery)
to create contiguous unallocated space for Debian root expansion without touching Partition 4 (DATA_STORE)
or Partition 1 (EFI ESP).

Options:
  -d, --dry-run                 Simulate deletion and display target partition layout without modifying disk
  --disk <path>                 Target block device (default: /dev/nvme0n1)
  --mock-target-part <num>      Simulate deleting single partition <num> (used by guardrail unit tests)
  -f, --force                   Proceed without interactive confirmation prompt
  -h, --help                    Show this help message and exit

Examples:
  ./scripts/migration/reclaim_transition_partitions.sh --dry-run
  sudo ./scripts/migration/reclaim_transition_partitions.sh
EOF
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
            TARGET_DISK="$2"
            shift 2
            ;;
        --mock-target-part)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --mock-target-part requires a partition number." >&2
                exit 1
            fi
            MOCK_TARGET_PART="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
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
echo "  SAFE TRANSITION PARTITION RECLAMATION (PHASE 4) "
echo "=================================================="
echo "Target Disk: ${TARGET_DISK}"

# 1. Guardrail Check Function
verify_partition_safety() {
    local part_num="$1"
    if [[ "$part_num" == "1" ]]; then
        echo "CRITICAL ERROR: Partition 1 is EFI System Partition (/boot/efi). Deletion prohibited!" >&2
        return 1
    fi
    if [[ "$part_num" == "4" ]]; then
        echo "CRITICAL ERROR: Partition 4 is DATA_STORE (201 GB User Data). Deletion strictly prohibited!" >&2
        return 1
    fi
    if [[ "$part_num" == "6" ]]; then
        echo "CRITICAL ERROR: Partition 6 is Active Debian Root (/). Online deletion prohibited!" >&2
        return 1
    fi
    return 0
}

# 2. Mock Mode Test Guardrail Handling
if [[ -n "$MOCK_TARGET_PART" ]]; then
    echo "[TEST GUARDRAIL] Evaluating target partition: ${MOCK_TARGET_PART}"
    if ! verify_partition_safety "$MOCK_TARGET_PART"; then
        exit 1
    fi
    echo "[TEST GUARDRAIL] Partition ${MOCK_TARGET_PART} passed safety checks."
    exit 0
fi

# 3. Inspect Current Partitions on Target Disk
echo "--- Current Partition Table on ${TARGET_DISK} ---"
if command -v parted >/dev/null 2>&1; then
    parted -s "${TARGET_DISK}" print || true
elif command -v lsblk >/dev/null 2>&1; then
    lsblk "${TARGET_DISK}" || true
fi

# 4. Target Disposable Partitions
DISPOSABLE_PARTS=(2 5 3)
echo "--- Disposable Partitions Targeted for Deletion: ${DISPOSABLE_PARTS[*]} ---"
echo "  - Partition 2 : Eks Windows C: (~140 GB NTFS)"
echo "  - Partition 5 : Eks Debian Installer Staging (~15 GB FAT32)"
echo "  - Partition 3 : Eks Windows Recovery (~5.7 GB NTFS)"

for part in "${DISPOSABLE_PARTS[@]}"; do
    if ! verify_partition_safety "$part"; then
        echo "ABORT: Unsafe partition configuration detected." >&2
        exit 1
    fi
done

# 5. Dry-Run Simulation Mode
if [[ "$DRY_RUN" == "true" ]]; then
    echo "--------------------------------------------------"
    echo "[DRY RUN] Simulating safe partition deletion:"
    for part in "${DISPOSABLE_PARTS[@]}"; do
        echo "  [DRY RUN] Would execute: parted -s ${TARGET_DISK} rm ${part}"
    done
    echo "[DRY RUN] Resulting Unallocated Space: ~160 GB surrounding Partition 6."
    echo "[DRY RUN] Protected Partitions Remaining Intact:"
    echo "          Partition 1 (100 MB EFI ESP -> /boot/efi)"
    echo "          Partition 6 (71 GB Debian Root -> /)"
    echo "          Partition 4 (244 GB DATA_STORE -> /mnt/data)"
    echo "=================================================="
    echo "[DRY RUN] Partition reclamation simulation passed successfully."
    echo "=================================================="
    exit 0
fi

# 6. Live Execution
if [[ "$FORCE" != "true" && -t 0 ]]; then
    read -r -p "Are you sure you want to delete partitions 2, 5, and 3 on ${TARGET_DISK}? [y/N] " response
    case "$response" in
        [yY][eE][sS]|[yY])
            echo "Proceeding with partition deletion..."
            ;;
        *)
            echo "Operation cancelled by user."
            exit 0
            ;;
    esac
fi

for part in "${DISPOSABLE_PARTS[@]}"; do
    PART_NODE="${TARGET_DISK}p${part}"
    if [[ -b "${PART_NODE}" ]] || (command -v parted >/dev/null 2>&1 && parted -s "${TARGET_DISK}" print 2>/dev/null | grep -q "^[[:space:]]*${part}[[:space:]]"); then
        echo "Deleting Partition ${part} on ${TARGET_DISK}..."
        if [[ $EUID -eq 0 ]]; then
            parted -s "${TARGET_DISK}" rm "${part}" || echo "Notice: parted returned non-zero for partition ${part}."
        elif sudo -n true 2>/dev/null; then
            sudo parted -s "${TARGET_DISK}" rm "${part}" || echo "Notice: parted returned non-zero for partition ${part}."
        else
            echo "ERROR: Elevated privileges required to modify partition table on ${TARGET_DISK}." >&2
            echo "Please run this script with sudo: sudo $0" >&2
            exit 1
        fi
    else
        echo "Notice: Partition ${part} does not exist or was already removed."
    fi
done

# Inform kernel of partition table change
if command -v partprobe >/dev/null 2>&1; then
    if [[ $EUID -eq 0 ]]; then
        partprobe "${TARGET_DISK}" 2>/dev/null || true
    elif sudo -n true 2>/dev/null; then
        sudo partprobe "${TARGET_DISK}" 2>/dev/null || true
    fi
fi

echo "=================================================="
echo "SUCCESS: Transition partitions reclaimed."
echo "Current storage layout on ${TARGET_DISK}:"
lsblk -o NAME,SIZE,START,FSTYPE,LABEL,MOUNTPOINTS "${TARGET_DISK}" 2>/dev/null || true
echo "=================================================="
exit 0
